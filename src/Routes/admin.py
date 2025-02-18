import uuid
import os
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import func
from Database.Models.admin import Admin
from Database.db import db
from functools import wraps
from dotenv import load_dotenv
import requests
from datetime import datetime, timedelta
from Database.Models.tickets import Ticket
from Database.Models.event_data import Event
from Database.Models.user import User
from Database.Models.promotions import Promotion
from Utlis.s3 import s3_handler

load_dotenv()

admin_bp = Blueprint('admin', __name__)

def admin_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form
        admin = Admin.query.filter_by(email=data.get('email')).first()
        verify_url = 'https://www.google.com/recaptcha/api/siteverify'
        recaptcha_secret = '6Ld-ydcqAAAAAPQxz_VJldSNl87rSrjH3qf1Z1Sf'
        recaptcha_response = request.form.get('g-recaptcha-response')
        recaptcha_data = {
            'secret': recaptcha_secret,
            'response': recaptcha_response
        }
        recaptcha_verify = requests.post(verify_url, data=recaptcha_data)
        recaptcha_result = recaptcha_verify.json()
        
        if not recaptcha_result.get('success'):
            return jsonify({
                'success': False,
                'error': 'Please complete the reCAPTCHA verification'
            }), 400
        
        if not admin or not admin.check_password(data.get('password')):
            return jsonify({
                'success': False,
                'error': 'Invalid email or password'
            }), 401
            
        session['admin_id'] = admin.id
        session['admin_email'] = admin.email
        session['admin_name'] = admin.name
        session.permanent = True
        
        return jsonify({
            'success': True,
            'redirect': url_for('admin.dashboard')
        })
            
    return render_template('Admin/login.html')

@admin_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('admin.login'))

@admin_bp.route('/dashboard')
@admin_login_required
def dashboard():
    total_transactions = Ticket.query.count()
    total_events = Event.query.count()
    valid_promotions = Promotion.query.filter(Promotion.valid_until >= datetime.now()).count()
    total_users = User.query.count()
    
    recent_transactions = Ticket.query.order_by(Ticket.purchase_date.desc()).limit(10).all()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=6)
    
    dates = []
    transaction_counts = []

    for i in range(7):
        current_date = start_date + timedelta(days=i)
        next_date = current_date + timedelta(days=1)
        date_string = current_date.strftime('%b %d')
        dates.append(date_string)
        daily_count = Ticket.query.filter(
            Ticket.purchase_date >= current_date,
            Ticket.purchase_date < next_date
        ).count()
        
        transaction_counts.append(daily_count)
    
    return render_template(
        'Admin/dashboard.html',
        total_transactions=total_transactions,
        total_events=total_events,
        total_promotions=valid_promotions,
        total_users=total_users,
        recent_transactions=recent_transactions,
        dates=dates,
        transaction_counts=transaction_counts
    )

@admin_bp.route('/settings')
def settings():
    pass


@admin_bp.route('/users')
@admin_login_required
def users():
    """Display all users with pagination and statistics"""
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of users per page
    users_pagination = User.query.paginate(page=page, per_page=per_page, error_out=False)
    total_users = User.query.count()
    verified_users = User.query.filter_by(is_verified=True).count()
    users_with_wallet = User.query.filter(User.eth_address.isnot(None)).count()
    
    return render_template(
        'admin/users.html',
        users=users_pagination.items,
        pagination=users_pagination,
        total_users=total_users,
        verified_users=verified_users,
        users_with_wallet=users_with_wallet
    )

@admin_bp.route('/users/<int:user_id>/tickets')
@admin_login_required
def user_tickets(user_id):
    """Display all tickets for a specific user"""
    user = User.query.get_or_404(user_id)
    tickets = Ticket.query.filter_by(user_id=user_id).all()
    
    return render_template(
        'admin/user_tickets.html',
        user=user,
        tickets=tickets
    )

@admin_bp.route('/users/<int:user_id>')
@admin_login_required
def view_user(user_id):
    """Display detailed information for a specific user"""
    user = User.query.get_or_404(user_id)
    tickets = Ticket.query.filter_by(user_id=user_id).all()
    
    # Get ticket statistics
    active_tickets = sum(1 for ticket in tickets if ticket.status == 'active')
    used_tickets = sum(1 for ticket in tickets if ticket.status == 'used')
    
    return render_template(
        'admin/view_user.html',
        user=user,
        tickets=tickets,
        active_tickets=active_tickets,
        used_tickets=used_tickets,
        total_tickets=len(tickets)
    )

@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_login_required
def edit_user(user_id):
    """Edit user information"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.fullname = request.form.get('fullname')
        user.email = request.form.get('email')
        user.is_verified = 'is_verified' in request.form
        
        try:
            db.session.commit()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'message': 'User information updated successfully',
                    'redirect': url_for('admin.users')  # Redirect to users list instead
                })
                
            flash('User information updated successfully', 'success')
            return redirect(url_for('admin.edit_user', user_id=user_id))  # Stay on edit page
        except Exception as e:
            db.session.rollback()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': f'Error updating user: {str(e)}'
                })
                
            flash(f'Error updating user: {str(e)}', 'error')
    
    return render_template('admin/user_edit.html', user=user)

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_login_required
def delete_user(user_id):
    """Delete a user and all their associated tickets"""
    try:
        user = User.query.get_or_404(user_id)
        tickets = Ticket.query.filter_by(user_id=user_id).all()
        for ticket in tickets:
            db.session.delete(ticket)
        db.session.delete(user)
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'User deleted successfully'})
        
        flash('User deleted successfully', 'success')
        return redirect(url_for('admin_users.users'))
    
    except Exception as e:
        db.session.rollback()
        error_message = f'Error deleting user: {str(e)}'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': error_message})
        
        flash(error_message, 'error')
        return redirect(url_for('admin_users.view_user', user_id=user_id))

@admin_bp.route('/users/search', methods=['GET'])
@admin_login_required
def search_users():
    """Search users by name or email"""
    search_term = request.args.get('term', '')
    
    if not search_term:
        return jsonify([])
    
    # Search for users by name or email
    users = User.query.filter(
        (User.fullname.ilike(f'%{search_term}%')) | 
        (User.email.ilike(f'%{search_term}%'))
    ).limit(10).all()
    
    # Format results
    results = [
        {
            'id': user.id,
            'fullname': user.fullname,
            'email': user.email,
            'is_verified': user.is_verified,
            'eth_address': user.eth_address if user.eth_address else None
        }
        for user in users
    ]
    
    return jsonify(results)

# API endpoints for admin dashboard
@admin_bp.route('/api/user-stats', methods=['GET'])
@admin_login_required
def user_stats():
    """Return user statistics for dashboard"""
    total_users = User.query.count()
    verified_users = User.query.filter_by(is_verified=True).count()
    users_with_wallet = User.query.filter(User.eth_address.isnot(None)).count()
    new_users_last_7_days = User.query.filter(
        func.date(User.created_at) >= func.date_sub(func.current_date(), 7)
    ).count()
    
    return jsonify({
        'total_users': total_users,
        'verified_users': verified_users,
        'users_with_wallet': users_with_wallet,
        'new_users_last_7_days': new_users_last_7_days
    })

@admin_bp.route('/users/report', methods=['GET'])
@admin_login_required
def generate_user_report():
    """Generate a report of all users"""
    users = User.query.all()
    
    # Get statistics for charts
    total_users = User.query.count()
    verified_users = User.query.filter_by(is_verified=True).count()
    users_with_wallet = User.query.filter(User.eth_address.isnot(None)).count()
    
    # Calculate ticket distribution
    users_with_no_tickets = User.query.filter(~User.tickets.any()).count()
    users_with_1_to_5_tickets = User.query.join(Ticket).group_by(User.id).having(func.count(Ticket.id).between(1, 5)).count()
    users_with_6_to_10_tickets = User.query.join(Ticket).group_by(User.id).having(func.count(Ticket.id).between(6, 10)).count()
    users_with_more_than_10_tickets = User.query.join(Ticket).group_by(User.id).having(func.count(Ticket.id) > 10).count()
    
    total_tickets = Ticket.query.count()
    report = []
    for user in users:
        tickets = Ticket.query.filter_by(user_id=user.id).all()
        active_tickets = sum(1 for ticket in tickets if ticket.status == 'active')
        user_data = {
            'id': user.id,
            'fullname': user.fullname,
            'email': user.email,
            'is_verified': user.is_verified,
            'has_wallet': user.eth_address is not None,
            'tickets_count': len(tickets),
            'active_tickets': active_tickets
        }
        report.append(user_data)
    
    if request.args.get('format') == 'json':
        return jsonify(report)
    
    return render_template(
        'admin/user_report.html',
        report=report,
        total_users=total_users,
        verified_users=verified_users,
        users_with_wallet=users_with_wallet,
        total_tickets=total_tickets,
        users_with_no_tickets=users_with_no_tickets,
        users_with_1_to_5_tickets=users_with_1_to_5_tickets,
        users_with_6_to_10_tickets=users_with_6_to_10_tickets,
        users_with_more_than_10_tickets=users_with_more_than_10_tickets
    )

@admin_bp.route('/events')
@admin_login_required
def events():
    """Display all events with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = 1
    
    events_pagination = Event.query.order_by(Event.event_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    total_events = Event.query.count()
    upcoming_events = Event.query.filter(Event.event_date >= datetime.now().date()).count()
    events_with_blockchain = Event.query.filter(Event.blockchain_event_id.isnot(None)).count()
    sold_tickets = {}
    for event in events_pagination.items:
        count = Ticket.query.filter_by(event_id=event.id).filter(Ticket.status != 'cancelled').count()
        sold_tickets[event.id] = count
    total_tickets_sold = Ticket.query.filter(Ticket.status != 'cancelled').count()
    now_date = datetime.now().date()
    
    return render_template(
        'admin/event.html',
        events=events_pagination.items,
        pagination=events_pagination,
        total_events=total_events,
        upcoming_events=upcoming_events,
        events_with_blockchain=events_with_blockchain,
        sold_tickets=sold_tickets, 
        total_tickets_sold=total_tickets_sold,  
        now_date=now_date, 
        blockchain_events=events_with_blockchain 
    )
@admin_bp.route('/events/create', methods=['GET', 'POST'])
@admin_login_required
def create_event():
    if request.method == 'POST':
        try:
            event_date = datetime.strptime(request.form['event_date'], '%Y-%m-%d').date()
            event_time = datetime.strptime(request.form['event_time'], '%H:%M').time()
            image_url = None
            if 'image' in request.files and request.files['image'].filename:
                image_url = s3_handler.upload_file(request.files['image'])
                if not image_url:
                    flash('Failed to upload image', 'error')
                    return redirect(request.url)
            
            new_event = Event(
                event_name=request.form['event_name'],
                available_tickets=int(request.form['available_tickets']),
                ticket_price=float(request.form['ticket_price']),
                venue=request.form['venue'],
                event_date=event_date,
                event_time=event_time,
                image_url=image_url,  
                description=request.form['description'],
                verification_pin=request.form.get('verification_pin'),
                eco_paper_straws='eco_paper_straws' in request.form,
                eco_public_transport='eco_public_transport' in request.form,
                eco_recycling='eco_recycling' in request.form,
                eco_composting='eco_composting' in request.form,
                eco_renewable_energy='eco_renewable_energy' in request.form
            )
            
            db.session.add(new_event)
            db.session.commit()
            
            if 'create_on_blockchain' in request.form:
                try:
                    new_event.create_on_blockchain()
                    flash('Event created and registered on blockchain successfully!', 'success')
                except Exception as e:
                    flash(f'Event created, but blockchain registration failed: {str(e)}', 'warning')
            else:
                flash('Event created successfully!', 'success')
            
            return redirect(url_for('admin.events'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating event: {str(e)}', 'error')
    
    return render_template('admin/event_create.html')

@admin_bp.route('/events/<int:event_id>')
@admin_login_required
def view_event(event_id):
    """Display detailed information for a specific event"""
    event = Event.query.get_or_404(event_id)
    total_tickets = Ticket.query.filter_by(event_id=event_id).count()
    sold_tickets = Ticket.query.filter_by(event_id=event_id).filter(Ticket.status != 'cancelled').count()
    used_tickets = Ticket.query.filter_by(event_id=event_id, status='used').count()
    
    return render_template(
        'admin/event_view.html',
        event=event,
        total_tickets=total_tickets,
        sold_tickets=sold_tickets,
        used_tickets=used_tickets
    )

admin_bp.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
@admin_login_required
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        try:
            event.event_name = request.form['event_name']
            event.available_tickets = int(request.form['available_tickets'])
            event.ticket_price = float(request.form['ticket_price'])
            event.venue = request.form['venue']
            event.event_date = datetime.strptime(request.form['event_date'], '%Y-%m-%d').date()
            event.event_time = datetime.strptime(request.form['event_time'], '%H:%M').time()
            event.description = request.form['description']
            event.verification_pin = request.form.get('verification_pin')
            event.eco_paper_straws = 'eco_paper_straws' in request.form
            event.eco_public_transport = 'eco_public_transport' in request.form
            event.eco_recycling = 'eco_recycling' in request.form
            event.eco_composting = 'eco_composting' in request.form
            event.eco_renewable_energy = 'eco_renewable_energy' in request.form
            
            if 'image' in request.files and request.files['image'].filename:
                if event.image_url:
                    s3_handler.delete_file(event.image_url)
                image_url = s3_handler.upload_file(request.files['image'])
                if image_url:
                    event.image_url = image_url
                else:
                    flash('Failed to upload new image', 'error')
            if 'remove_image' in request.form and event.image_url:
                s3_handler.delete_file(event.image_url)
                event.image_url = None
            
            db.session.commit()
            flash('Event updated successfully!', 'success')
            return redirect(url_for('admin.view_event', event_id=event_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating event: {str(e)}', 'error')
    
    return render_template(
        'admin/event_edit.html', 
        event=event,
        now_date=datetime.now().date()
    )

@admin_bp.route('/events/<int:event_id>/delete', methods=['POST'])
@admin_login_required
def delete_event(event_id):
    try:
        event = Event.query.get_or_404(event_id)
        
        if Ticket.query.filter_by(event_id=event_id).count() > 0:
            flash('Cannot delete event with associated tickets', 'error')
            return redirect(url_for('admin.view_event', event_id=event_id))
        if event.image_url:
            s3_handler.delete_file(event.image_url)
        
        db.session.delete(event)
        db.session.commit()
        
        flash('Event deleted successfully', 'success')
        return redirect(url_for('admin.events'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting event: {str(e)}', 'error')
        return redirect(url_for('admin.events'))

@admin_bp.route('/events/<int:event_id>/edit', methods=['GET', 'POST'])
@admin_login_required
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        try:
            event.event_name = request.form['event_name']
            event.available_tickets = int(request.form['available_tickets'])
            event.ticket_price = float(request.form['ticket_price'])
            event.venue = request.form['venue']
            event.event_date = datetime.strptime(request.form['event_date'], '%Y-%m-%d').date()
            event.event_time = datetime.strptime(request.form['event_time'], '%H:%M').time()
            event.description = request.form['description']
            event.verification_pin = request.form.get('verification_pin')
            event.eco_paper_straws = 'eco_paper_straws' in request.form
            event.eco_public_transport = 'eco_public_transport' in request.form
            event.eco_recycling = 'eco_recycling' in request.form
            event.eco_composting = 'eco_composting' in request.form
            event.eco_renewable_energy = 'eco_renewable_energy' in request.form
            
            if 'image' in request.files and request.files['image'].filename:
                # Delete old image if exists
                if event.image_url:
                    s3_handler.delete_file(event.image_url)
                
                image_url = s3_handler.upload_file(request.files['image'])
                if image_url:
                    event.image_url = image_url
                else:
                    flash('Failed to upload new image', 'error')
            
            if 'remove_image' in request.form and event.image_url:
                s3_handler.delete_file(event.image_url)
                event.image_url = None
            
            db.session.commit()
            flash('Event updated successfully!', 'success')
            return redirect(url_for('admin.view_event', event_id=event_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating event: {str(e)}', 'error')
    
    return render_template(
        'admin/event_edit.html', 
        event=event,
        now_date=datetime.now().date()
    )


    
@admin_bp.route('/events/search', methods=['GET'])
@admin_login_required
def search_events():
    """Search events by name, venue, or description"""
    search_term = request.args.get('term', '').strip()
    filter_type = request.args.get('filter', '')
    
    if not search_term:
        return jsonify([])
    query = Event.query
    search_pattern = f"%{search_term}%"
    query = query.filter(
        db.or_(
            Event.event_name.ilike(search_pattern),
            Event.venue.ilike(search_pattern),
            Event.description.ilike(search_pattern)
        )
    )
    now_date = datetime.now().date()
    if filter_type == 'upcoming':
        query = query.filter(Event.event_date >= now_date)
    elif filter_type == 'past':
        query = query.filter(Event.event_date < now_date)
    elif filter_type == 'blockchain':
        query = query.filter(Event.blockchain_event_id.isnot(None))
    events = query.order_by(Event.event_date.desc()).limit(10).all()
    
    results = [
        {
            'id': event.id,
            'event_name': event.event_name,
            'venue': event.venue,
            'event_date': event.event_date.strftime('%Y-%m-%d'),
            'available_tickets': event.available_tickets,
            'blockchain_event_id': event.blockchain_event_id,
            'status': 'upcoming' if event.event_date >= now_date else 'past',
            'total_tickets': event.available_tickets,
            'sold_tickets': Ticket.query.filter_by(event_id=event.id).filter(Ticket.status != 'cancelled').count()
        }
        for event in events
    ]
    
    return jsonify(results)

@admin_bp.route('/promotions')
@admin_login_required
def promotions():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    status = request.args.get('status', 'all')
    per_page = 10
    query = Promotion.query
    if search:
        query = query.filter(
            db.or_(
                Promotion.title.ilike(f'%{search}%'),
                Promotion.description.ilike(f'%{search}%')
            )
        )
    
    now = datetime.now()
    if status == 'active':
        query = query.filter(
            db.and_(
                Promotion.status == 'active',
                Promotion.valid_until > now
            )
        )
    elif status == 'expired':
        query = query.filter(
            db.or_(
                Promotion.status == 'expired',
                Promotion.valid_until <= now
            )
        )
    
    promotions_pagination = query.order_by(Promotion.valid_until.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    total_promotions = Promotion.query.count()
    active_promotions = Promotion.query.filter(
        db.and_(
            Promotion.status == 'active',
            Promotion.valid_until > now
        )
    ).count()
    expired_promotions = total_promotions - active_promotions
    
    return render_template(
        'admin/promotions.html',
        promotions=promotions_pagination.items,
        pagination=promotions_pagination,
        total_promotions=total_promotions,
        active_promotions=active_promotions,
        expired_promotions=expired_promotions
    )

@admin_bp.route('/promotions/create', methods=['GET', 'POST'])
@admin_login_required
def create_promotion():
    if request.method == 'POST':
        try:
            # Parse date and time
            valid_until = datetime.strptime(
                f"{request.form['valid_until_date']} {request.form['valid_until_time']}", 
                '%Y-%m-%d %H:%M'
            )
            
            image_url = None
            if 'image' in request.files and request.files['image'].filename:
                file = request.files['image']
            new_promotion = Promotion(
                title=request.form['title'],
                description=request.form['description'],
                valid_until=valid_until,
                status='active',
                image_url=image_url
            )
            
            db.session.add(new_promotion)
            db.session.commit()
            
            flash('Promotion created successfully!', 'success')
            return redirect(url_for('admin.promotions'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating promotion: {str(e)}', 'error')
    
    return render_template('admin/promotion_form.html', promotion=None)

@admin_bp.route('/promotions/<int:promotion_id>/edit', methods=['GET', 'POST'])
@admin_login_required
def edit_promotion(promotion_id):
    promotion = Promotion.query.get_or_404(promotion_id)
    
    if request.method == 'POST':
        try:
            valid_until = datetime.strptime(
                f"{request.form['valid_until_date']} {request.form['valid_until_time']}", 
                '%Y-%m-%d %H:%M'
            )
            
            promotion.title = request.form['title']
            promotion.description = request.form['description']
            promotion.valid_until = valid_until
            promotion.status = request.form.get('status', 'active')
            
            if 'image' in request.files and request.files['image'].filename:
                file = request.files['image']            
            if 'remove_image' in request.form and promotion.image_url:
                promotion.image_url = None
            
            db.session.commit()
            flash('Promotion updated successfully!', 'success')
            return redirect(url_for('admin.promotions'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating promotion: {str(e)}', 'error')
    
    return render_template('admin/promotion_form.html', promotion=promotion)

# Delete promotion
@admin_bp.route('/promotions/<int:promotion_id>/delete', methods=['POST'])
@admin_login_required
def delete_promotion(promotion_id):
    promotion = Promotion.query.get_or_404(promotion_id)
    
    try:
        if promotion.image_url:
            pass
        db.session.delete(promotion)
        db.session.commit()
        flash('Promotion deleted successfully!', 'success')
        return redirect(url_for('admin.promotions'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting promotion: {str(e)}', 'error')
        return redirect(url_for('admin.promotions'))