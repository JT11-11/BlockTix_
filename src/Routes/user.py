import hashlib
import os
import smtplib
from datetime import datetime, timedelta
from decimal import Decimal
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import wraps
from io import BytesIO
import requests
from eth_account import Account
from flask import (Blueprint, flash, jsonify, redirect, render_template,
                  request, session, url_for)
from mindee import Client, product
from web3 import Web3
from werkzeug.utils import secure_filename
from Database.db import db
from Database.Models.event_data import Event
from Database.Models.promotions import Promotion
from Database.Models.tickets import Ticket
from Database.Models.user import User
from Utlis.web3_config import contract_service, w3
from dotenv import load_dotenv
from Utlis.Users.email import generate_verification_code,send_verification_email
from Utlis.Users.blockchain import create_eth_account
from Utlis.Users.ticket import generate_ticket_id,send_ticket_confirmation
from Utlis.Users.login import login_required

load_dotenv()

user_bp = Blueprint('user', __name__)
mindee_client = Client(os.environ.get('MINDEE_API_KEY'))

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form
        user = User.query.filter_by(email=data.get('email')).first()
        verify_url = 'https://www.google.com/recaptcha/api/siteverify'
        recaptcha_secret = os.environ.get('RECAPTCHA_SECRET')
        
        if not user or not user.check_password(data.get('password')):
            return jsonify({
                'success': False, 
                'error': 'Invalid email or password'
            }), 401
        
        verification_code = generate_verification_code()
        session['verification_code'] = verification_code
        session['code_expiry'] = (datetime.now() + timedelta(minutes=10)).timestamp()
        session['user_id'] = user.id
        session['user_email'] = user.email
        session['eth_address'] = user.eth_address
        session['user_fullname'] = user.fullname

        session.permanent = True
        
        if send_verification_email(user.email, verification_code):
            return jsonify({'success': True, 'redirect': url_for('user.mfa')})
        else:
            return jsonify({'success': False, 'error': 'Failed to send verification code'}), 500
            
    return render_template('User/login.html')

@user_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('user.login'))

@user_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        recaptcha_response = request.form.get('g-recaptcha-response')


        verify_url = 'https://www.google.com/recaptcha/api/siteverify'
        recaptcha_secret = os.environ.get('RECAPTCHA_SECRET')
        recaptcha_data = {
            'secret': recaptcha_secret,
            'response': recaptcha_response
        }
        recaptcha_verify = requests.post(verify_url, data=recaptcha_data)
        recaptcha_result = recaptcha_verify.json()

        
        if not all([fullname, email, password, confirm_password]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400
            
        if password != confirm_password:
            return jsonify({'success': False, 'error': 'Passwords do not match'}), 400
            
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': 'Email already registered'}), 400
        
        try:
            eth_account = create_eth_account() 
            print(f"Created Ethereum account: {eth_account['address']}")
        except Exception as e:
            return jsonify({
                'success': False, 
                'error': f'Failed to create blockchain account: {str(e)}'
            }), 500

        try:
            user = User(fullname=fullname, email=email, eth_address=eth_account['address'])            
            user.set_password(password)
            user.set_eth_private_key(eth_account['private_key'])  
            db.session.add(user)
            db.session.commit()
            
            verification_code = generate_verification_code()
            session['verification_code'] = verification_code
            session['code_expiry'] = (datetime.now() + timedelta(minutes=10)).timestamp()
            session['user_id'] = user.id
            session['user_email'] = user.email
            session['eth_address'] = eth_account['address']
        
                        
            if send_verification_email(email, verification_code):
                return jsonify({'success': True, 'redirect': url_for('user.mfa')})
            else:
                return jsonify({'success': False, 'error': 'Failed to send verification code'}), 500

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'An error occurred. Please try again.'}), 500
            
    return render_template('User/signup.html')

@user_bp.route('/verify', methods=['GET', 'POST'])
@login_required
def verify():
    if request.method == 'POST':
        if 'idDocument' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
            
        file = request.files['idDocument']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
            
        try:
            temp_path = os.path.join('/tmp', secure_filename(file.filename))
            file.save(temp_path)

            my_endpoint = mindee_client.create_endpoint(
                account_name="Jasper08",
                endpoint_name="id_card",
                version="1"
            )

            input_doc = mindee_client.source_from_path(temp_path)
            result = mindee_client.enqueue_and_parse(
                product.GeneratedV1,
                input_doc,
                endpoint=my_endpoint
            )
            nric_found = False
            for field_name, field_values in result.document.inference.prediction.fields.items():
                if field_name == 'nric_number':
                    nric_found = True
                    nric_number = hashlib.sha256(str(field_values).encode()).hexdigest()
                    existing_user = User.query.filter_by(id_number_hash=nric_number).first()
                    if existing_user:
                        os.remove(temp_path)
                        return jsonify({
                            'success': False,
                            'error': 'This NRIC is already registered'
                        }), 400
                    
                    user = User.query.get(session['user_id'])
                    user.set_id_number(str(field_values))
                    user.is_verified = True
                    db.session.commit()
                    os.remove(temp_path)
                    return jsonify({
                        'success': True,
                        'redirect': url_for('user.dashboard')
                    })
            
            if not nric_found:
                return jsonify({'success': False, 'error': 'Could not extract NRIC number'}), 400
                
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({'success': False, 'error': str(e)}), 500
            
    return render_template('User/verify.html')

@user_bp.route('/mfa', methods=['GET', 'POST'])
def mfa():
    if request.method == 'POST':
        entered_code = ''.join(request.form.getlist('code[]'))
        stored_code = session.get('verification_code')
        code_expiry = session.get('code_expiry')
        
        if not code_expiry or datetime.now().timestamp() > code_expiry:
            session.pop('verification_code', None)
            session.pop('code_expiry', None)
            return jsonify({'success': False, 'error': 'Verification code has expired'}), 400
            
        if stored_code and stored_code == entered_code:
            session.pop('verification_code', None)
            session.pop('code_expiry', None)
            user = User.query.get(session['user_id'])
            if not user.is_verified:
                return jsonify({'success': True, 'redirect': url_for('user.verify')})
            return jsonify({'success': True, 'redirect': url_for('user.dashboard')})
        else:
            return jsonify({'success': False, 'error': 'Invalid verification code'}), 400
            
    return render_template('User/emailauth.html')

@user_bp.route('/resend_code', methods=['POST'])
def resend_code():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'error': 'No email found'}), 400
        
    verification_code = generate_verification_code()
    session['verification_code'] = verification_code
    session['code_expiry'] = (datetime.utcnow() + timedelta(minutes=10)).timestamp()
    
    if send_verification_email(user_email, verification_code):
        return jsonify({'success': True, 'message': 'New code sent successfully'})
    else:
        return jsonify({'success': False, 'error': 'Failed to send new code'}), 500


@user_bp.route('/dashboard')
@login_required
def dashboard():
    user_tickets = Ticket.query.filter_by(user_id=session['user_id']).all()
    time_now=datetime.now()
    active_promotions = Promotion.query.filter(
        Promotion.valid_until >= time_now
    ).all()
    
    return render_template('User/dashboard.html', 
                         tickets=user_tickets,
                         promotions=active_promotions)

@user_bp.route('/events')
@login_required
def events():
    events_list = Event.query.all()
    return render_template('User/events.html', events=events_list)

@user_bp.route('/event/<int:event_id>')
@login_required
def event_details(event_id):
    try:
        event = Event.query.get_or_404(event_id)
        return jsonify({
            'id': event.id,
            'name': event.event_name,
            'available_tickets': event.available_tickets,
            'ticket_price': float(event.ticket_price),
            'venue': event.venue,
            'date': event.event_date.strftime('%B %d, %Y'),  
            'time': event.event_time.strftime('%I:%M %p'),   
            'image_url': event.image_url,  
            'description': event.description,
            'eco_paper_straws': event.eco_paper_straws,
            'eco_public_transport': event.eco_public_transport,
            'eco_recycling': event.eco_recycling,
            'eco_composting': event.eco_composting,
            'eco_renewable_energy': event.eco_renewable_energy
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_bp.route('/buy-ticket/<int:event_id>', methods=['GET', 'POST'])
@login_required
def buy_ticket(event_id):
    print(f"Accessing buy_ticket route for event {event_id}")
    try:
        event = Event.query.get_or_404(event_id)
        user = User.query.get(session['user_id'])
        
        ticket_price = Decimal(str(event.ticket_price))  
        service_fee = ticket_price * Decimal('0.05')     
        total_amount = ticket_price + service_fee
        
        context = {
            'event': event,
            'user': user,
            'service_fee': service_fee,
            'total_amount': total_amount,
            'ticket_price': ticket_price 
        }
        
        if event.available_tickets <= 0:
            context['error'] = "Sorry, this event is sold out."
        elif event.event_date < datetime.now().date():
            context['error'] = "This event has already passed."
        else:
            existing_ticket = Ticket.query.filter_by(
                user_id=session['user_id'],
                event_id=event_id,
                status='active'
            ).first()
            
            if existing_ticket:
                context['error'] = "You already have an active ticket for this event."
        
        return render_template('User/buy_ticket.html', **context)
                             
    except Exception as e:
        print(f"Error in buy_ticket: {str(e)}")
        return redirect(url_for('user.events'))
    
@user_bp.route('/process_payment/<int:event_id>', methods=['POST'])
@login_required
def process_payment(event_id):
    try:
        event = Event.query.get_or_404(event_id)
        user = User.query.get(session['user_id'])

        print(f"Processing payment for event {event_id}")
        print(f"User ETH address: {user.eth_address}")

        if event.available_tickets <= 0:
            return jsonify({'success': False, 'error': 'Event is sold out'}), 400

        existing_ticket = Ticket.query.filter_by(
            user_id=session['user_id'],
            event_id=event_id,
            status='active'
        ).first()
        
        if existing_ticket:
            return jsonify({'success': False, 'error': 'You already have a ticket'}), 400

        try:
            print("Starting NFT minting process...")
            blockchain_ticket_id = contract_service.mint_ticket(
                to_address=user.eth_address,
                event_name=event.event_name,
                event_date=event,
                venue=event.venue
            )
            print(f"Successfully minted token ID: {blockchain_ticket_id}")

            ticket_id = generate_ticket_id()
            new_ticket = Ticket(
                user_id=session['user_id'],
                event_id=event_id,
                amount_paid=event.ticket_price,
                ticket_id=ticket_id,
                status='active'
            )
            
            new_ticket.blockchain_ticket_id = str(blockchain_ticket_id)
            event.available_tickets -= 1
            db.session.add(new_ticket)
            db.session.commit()
            print(f"Saved ticket to database with ID: {ticket_id}")

            ticket_details = {
                'event_name': event.event_name,
                'event_date': event.event_date.strftime('%B %d, %Y'),
                'event_time': event.event_time.strftime('%I:%M %p'),
                'venue': event.venue,
                'ticket_id': ticket_id
            }
            
            send_ticket_confirmation(user.email, ticket_details)
            print("Sent confirmation email")

            return jsonify({
                'success': True, 
                'message': 'Ticket purchased successfully',
                'redirect': url_for('user.dashboard')
            })

        except Exception as e:
            print(f"Error in minting process: {str(e)}")
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': f'Purchase failed: {str(e)}'
            }), 500

    except Exception as e:
        print(f"General error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
@user_bp.route('/verify-ticket/<string:ticket_id>', methods=['POST'])
@login_required
def verify_ticket(ticket_id):
    try:
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'error': 'Please log in to verify ticket'
            }), 401

        user_id = session['user_id']
        data = request.get_json()
        
        print(f"\n=== Ticket Verification Debug ===")
        print(f"Session data: {session}")
        print(f"User ID from session: {user_id}")
        print(f"Looking up ticket: {ticket_id}")
        
        ticket = Ticket.query.filter_by(ticket_id=ticket_id).first()
        
        if not ticket:
            return jsonify({
                'success': False,
                'error': 'Ticket not found'
            }), 404
        if ticket.user_id != user_id:
            return jsonify({
                'success': False,
                'error': 'Ticket does not belong to current user'
            }), 403
        
        pin = data.get('pin')
        if not pin:
            return jsonify({
                'success': False,
                'error': 'Verification pin required'
            }), 400
        event = Event.query.get(ticket.event_id)
        if not event:
            return jsonify({
                'success': False,
                'error': 'Event not found'
            }), 404

        success, message = ticket.generate_qr_code(pin)
        if not success:
            return jsonify({
                'success': False,
                'error': message
            }), 400

        return jsonify({
            'success': True,
            'qr_code': ticket.qr_code,
            'ticket_details': ticket.to_dict()
        })

    except Exception as e:
        print(f"Error in verify_ticket: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Verification failed: {str(e)}'
        }), 500
    
@user_bp.route('/promotions')
@login_required
def promotions():
    time_now = datetime.now()    
    all_promotions = Promotion.query.all()    
    active_promotions = []
    expired_promotions = []
    
    for promo in all_promotions:
        if promo.valid_until > time_now and promo.status == 'active':
            active_promotions.append(promo)
        else:
            expired_promotions.append(promo)
    
    active_promotions.sort(key=lambda x: x.valid_until)
    expired_promotions.sort(key=lambda x: x.valid_until, reverse=True)
    
    promotions = {
        'active': active_promotions,
        'expired': expired_promotions
    }
    
    return render_template(
        'User/promotions.html',
        promotions=promotions,
        current_time=time_now
    )

@user_bp.route('/submit_contact', methods=['POST'])
@login_required
def submit_contact():
    try:
        print("Incoming request data:", request.get_json())
        if not request.is_json:
            print("Invalid content type")
            return jsonify({
                'success': False,
                'error': 'Invalid content type, expected JSON'
            }), 400

        data = request.get_json()
        
        if not data.get('type') or not data.get('budget'):
            print(f"Missing required fields. Type: {data.get('type')}, Budget: {data.get('budget')}")
            return jsonify({
                'success': False,
                'error': 'Type and budget are required'
            }), 400

        user = User.query.get(session['user_id'])
        
        additional_info = data.get('additionalInfo', '').strip()
        if not additional_info:
            additional_info = 'Not provided'
        
        admin_msg = MIMEMultipart()
        admin_msg['From'] = os.environ.get('EMAIL_USER')
        admin_msg['To'] = os.environ.get('EMAIL_USER')
        admin_msg['Subject'] = "New Contact Form Submission"
        
        admin_body = f"""
        New Contact Form Submission
        -------------------------
        From: {user.fullname}
        Email: {user.email}
        
        Type: {data.get('type')}
        Budget: {data.get('budget')}
        
        Additional Information:
        {additional_info}
        
        Submitted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        admin_msg.attach(MIMEText(admin_body, 'plain'))
        
        user_msg = MIMEMultipart()
        user_msg['From'] = os.environ.get('EMAIL_USER')
        user_msg['To'] = user.email
        user_msg['Subject'] = "Thank you for contacting Summerly Media"
        
        user_body = f"""
        Hi {user.fullname},
        
        Thank you for reaching out to Summerly Media! We've received your message and will get back to you soon.
        
        Here's a summary of your submission:
        
        Type of Service: {data.get('type')}
        Budget Range: {data.get('budget')}
        Additional Information: {additional_info}
        
        We'll review your request and get back to you shortly.
        
        Best regards,
        Summerly Media Team
        """
        
        user_msg.attach(MIMEText(user_body, 'plain'))
        
        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login("blocktix4@gmail.com", "vtct tuxw umbi whnj")
                
                server.send_message(admin_msg)
                print("Admin email sent successfully")
                
                server.send_message(user_msg)
                print("User email sent successfully")
                
        except Exception as email_error:
            print(f"Email error: {str(email_error)}")
            return jsonify({
                'success': False,
                'error': 'Failed to send email. Please try again.'
            }), 500
        
        return jsonify({
            'success': True,
            'message': 'Your message has been sent successfully!'
        })
        
    except Exception as e:
        print(f"Error in submit_contact: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to send message. Please try again.'
        }), 500
    
@user_bp.route('/contact')
@login_required
def contact():
    user = User.query.get(session['user_id'])
    return render_template('User/contact.html', user=user)

@user_bp.route('/image/<event_id>')
@login_required
def get_event_image(event_id):
    try:
        event = Event.query.get_or_404(event_id)
        if event.image_url:
            return redirect(event.image_url)
        else:
            return redirect(url_for('static', filename='placeholder.jpg'))
    except Exception as e:
        print(f"Error getting image: {str(e)}")
        return redirect(url_for('static', filename='placeholder.jpg'))