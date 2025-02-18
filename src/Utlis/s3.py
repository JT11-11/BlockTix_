from botocore.exceptions import ClientError
import boto3
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

class S3Handler:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_REGION')    
        )
        self.bucket_name =os.environ.get('AWS_S3_BUCKET')

    def upload_file(self, file_obj):
        """Upload a file to S3 bucket"""
        try:
            file_extension = os.path.splitext(file_obj.filename)[1]
            unique_filename = f"Events/{str(uuid.uuid4())}{file_extension}"  

            # Upload file
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                unique_filename,
                ExtraArgs={
                    'ContentType': file_obj.content_type,
                }
            )

            # Generate URL
            url = f"https://{self.bucket_name}.s3.amazonaws.com/{unique_filename}"
            return url

        except ClientError as e:
            print(f"Error uploading to S3: {str(e)}")
            return None

    def delete_file(self, file_url):
        """Delete a file from S3 bucket"""
        try:
            # Extract key from URL
            key = file_url.split(f"https://{self.bucket_name}.s3.amazonaws.com/")[1]
            
            # Delete file
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except ClientError as e:
            print(f"Error deleting from S3: {str(e)}")
            return False

s3_handler = S3Handler()