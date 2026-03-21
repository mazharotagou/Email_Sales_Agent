from quart import Quart
import smtplib
from email.message import EmailMessage
import imaplib
import email
from dotenv import load_dotenv
import os


load_dotenv()
gmail_user = os.getenv("GMAIL_USERNAME")
gmail_password = os.getenv("GMAIL_PASSWORD")

app = Quart(__name__)

def send_email():
    # Create Email Object
    msg = EmailMessage()
    msg['Subject'] = 'Test Email'
    msg['From'] = gmail_user
    msg['To'] = 'mazharotagou@gmail.com'
    msg.set_content('Body of the email')

    # Send Email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(gmail_user, gmail_password)
        smtp.send_message(msg)

def recieve_email():
    # Connect to IMAP Server
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(gmail_user, gmail_password)
    mail.select('inbox')
    # Search for emails
    result, data = mail.search(None, 'UNSEEN')
    for num in data[0].split():
        # Fetch and parse email data
        typ, data = mail.fetch(num, '(RFC822)')
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        print(msg["Subject"])




@app.route('/')
async def hello():
    #send_email()
    recieve_email()
    return 'hello'

app.run()