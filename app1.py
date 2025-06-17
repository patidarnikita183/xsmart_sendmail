import sqlite3
import threading
import time
import json
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, redirect, send_file
from flask_socketio import SocketIO, emit
import base64
import io
from urllib.parse import quote, unquote
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*")

# Real email addresses for testing
REAL_EMAIL_ADDRESSES = [
    'patidarnikita183@gmail.com',
    'nikitapatidar.xalt@gmail.com',
    'nikita.patidar@xaltanalytics.com'
]

# Email configuration (you'll need to set these)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "patidarnikita183@gmail.com"  # Replace with your email
SENDER_PASSWORD = 'czjq bnds wlyg mmfy'  # Replace with your app password
SENDER_NAME = "Campaign Tracker"
import uuid
# Base URL for tracking (update this with your actual domain)
# BASE_URL = "http://localhost:5000" 
#  # Change to your actual domain
BASE_URL = "https://453f-106-222-217-143.ngrok-free.app"

# TEST_CAMPAIGN_ID = str(uuid.uuid4())
import uuid

def get_unique_int():
    u = uuid.uuid4()
    return u.int >> 96
TEST_CAMPAIGN_ID = get_unique_int()

def init_tracking_db():
    """Initialize database with real email addresses"""
    conn = sqlite3.connect('real_tracking.db')
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sent_at TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            email TEXT NOT NULL,
            tracking_id TEXT UNIQUE NOT NULL,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivery_status TEXT DEFAULT 'pending'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_opens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id TEXT,
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS link_clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id TEXT,
            url TEXT,
            clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analytics_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            total_sent INTEGER,
            unique_opens INTEGER,
            total_opens INTEGER,
            unique_clicks INTEGER,
            total_clicks INTEGER,
            open_rate REAL,
            click_rate REAL,
            snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check if test campaign exists
    cursor.execute('SELECT COUNT(*) FROM campaigns WHERE id = ?', (TEST_CAMPAIGN_ID,))
    if cursor.fetchone()[0] == 0:
        # Create test campaign
        campaign_content = f"""
            
            <div style="padding: 30px; background: #f8f9fa;">
                <h2>Hello! 👋</h2>
                <p>This is a test email for our real-time campaign tracking system.</p>
                
                <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3>🎯 What we're tracking:</h3>
                    <ul>
                        <li>✅ Email opens (when you view this email)</li>
                        <li>🖱️ Link clicks (when you click any link below)</li>
                        <li>⏰ Real-time analytics updates every 2 minutes</li>
                        <li>📊 Live performance metrics</li>
                    </ul>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="https://github.com" style="display: inline-block; background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 5px;">
                        🔗 Visit GitHub
                    </a>
                    <a href="https://stackoverflow.com" style="display: inline-block; background: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 5px;">
                        🔗 Visit StackOverflow
                    </a>
                    <a href="https://google.com" style="display: inline-block; background: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 5px;">
                        🔗 Visit Google
                    </a>
                </div>
                
                <div style="background: #e9ecef; padding: 15px; border-radius: 5px; font-size: 14px;">
                    <strong>📈 Analytics Dashboard:</strong><br>
                    Check <code>{BASE_URL}/api/analytics/current</code> for live stats!
                </div>
            </div>
            
            <div style="background: #343a40; color: white; padding: 20px; text-align: center; font-size: 12px;">
                <p>Campaign ID: {TEST_CAMPAIGN_ID} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>This email was sent for testing purposes.</p>
            </div>
        </body>
        </html>
        """
        
        cursor.execute(
            'INSERT INTO campaigns (id, name, subject, content, status) VALUES (?, ?, ?, ?, ?)',
            (TEST_CAMPAIGN_ID, 'Real Email Tracking Test', '🚀 Email Tracking System Test', campaign_content, 'ready')
        )
    
    conn.commit()
    conn.close()
    print(f"✅ Database initialized with campaign ID: {TEST_CAMPAIGN_ID}")

def generate_tracking_id():
    """Generate unique tracking ID"""
    return secrets.token_urlsafe(16)

def add_link_tracking(content, tracking_id):
    """Add tracking to all links in email content"""
    import re
    print("content -------",content)
    print("tracking id ",tracking_id)
    def replace_link(match):
        original_url = match.group(1)
        if original_url.startswith('http'):
            tracking_url = f"{BASE_URL}/track/click/{tracking_id}/{quote(original_url, safe='')}"
            return f'href="{tracking_url}"'
        return match.group(0)
    
    tracked_content = re.sub(r'href=["\']([^"\']+)["\']', replace_link, content)
    
    # Add visible tracking pixel for testing
    tracking_pixel = f'<img src="{BASE_URL}/track/open/{tracking_id}" width="50" height="50" style="border: 2px solid red; margin: 10px;" alt="Tracking Pixel">'
    final_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="text-align: center; padding: 10px; background: #f0f0f0; margin-bottom: 20px;">
            <p style="margin: 0; color: #666;">Tracking Pixel (For Testing)</p>
            {tracking_pixel}
        </div>
        {tracked_content}
    </body>
    </html>
    """
    print("tracking_pixel", tracking_pixel)
    print("final_content", final_content)
    
    return final_content

def send_real_email(to_email, subject, html_content):
    """Send actual email via SMTP"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg['To'] = to_email
        
        # Add HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {str(e)}")
        return False

def get_campaign_analytics(campaign_id):
    """Calculate real-time campaign analytics"""
    try:
        conn = sqlite3.connect('real_tracking.db')
        cursor = conn.cursor()
        
        # Total recipients
        cursor.execute('SELECT COUNT(*) FROM recipients WHERE campaign_id = ?', (campaign_id,))
        total_sent = cursor.fetchone()[0]
        
        if total_sent == 0:
            conn.close()
            return None
        
        # Unique opens
        cursor.execute('''
            SELECT COUNT(DISTINCT r.tracking_id) 
            FROM recipients r 
            JOIN email_opens eo ON r.tracking_id = eo.tracking_id 
            WHERE r.campaign_id = ?
        ''', (campaign_id,))
        unique_opens = cursor.fetchone()[0]
        
        # Total opens
        cursor.execute('''
            SELECT COUNT(*) 
            FROM recipients r 
            JOIN email_opens eo ON r.tracking_id = eo.tracking_id 
            WHERE r.campaign_id = ?
        ''', (campaign_id,))
        total_opens = cursor.fetchone()[0]
        
        # Unique clicks
        cursor.execute('''
            SELECT COUNT(DISTINCT r.tracking_id) 
            FROM recipients r 
            JOIN link_clicks lc ON r.tracking_id = lc.tracking_id 
            WHERE r.campaign_id = ?
        ''', (campaign_id,))
        unique_clicks = cursor.fetchone()[0]
        
        # Total clicks
        cursor.execute('''
            SELECT COUNT(*) 
            FROM recipients r 
            JOIN link_clicks lc ON r.tracking_id = lc.tracking_id 
            WHERE r.campaign_id = ?
        ''', (campaign_id,))
        total_clicks = cursor.fetchone()[0]
        
        # Recent activity (last 2 minutes)
        two_minutes_ago = (datetime.now() - timedelta(minutes=2)).isoformat()
        cursor.execute('''
            SELECT COUNT(*) 
            FROM recipients r 
            JOIN email_opens eo ON r.tracking_id = eo.tracking_id 
            WHERE r.campaign_id = ? AND eo.opened_at > ?
        ''', (campaign_id, two_minutes_ago))
        recent_opens = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) 
            FROM recipients r 
            JOIN link_clicks lc ON r.tracking_id = lc.tracking_id 
            WHERE r.campaign_id = ? AND lc.clicked_at > ?
        ''', (campaign_id, two_minutes_ago))
        recent_clicks = cursor.fetchone()[0]
        
        # Get recipient details
        cursor.execute('''
            SELECT r.email, r.tracking_id, r.delivery_status,
                   COUNT(DISTINCT eo.id) as opens,
                   COUNT(DISTINCT lc.id) as clicks
            FROM recipients r
            LEFT JOIN email_opens eo ON r.tracking_id = eo.tracking_id
            LEFT JOIN link_clicks lc ON r.tracking_id = lc.tracking_id
            WHERE r.campaign_id = ?
            GROUP BY r.email, r.tracking_id, r.delivery_status
        ''', (campaign_id,))
        
        recipient_details = []
        for row in cursor.fetchall():
            recipient_details.append({
                'email': row[0],
                'tracking_id': row[1],
                'delivery_status': row[2],
                'opens': row[3],
                'clicks': row[4]
            })
        
        conn.close()
        
        # Calculate rates
        open_rate = (unique_opens / total_sent * 100) if total_sent > 0 else 0
        click_rate = (unique_clicks / total_sent * 100) if total_sent > 0 else 0
        click_to_open_rate = (unique_clicks / unique_opens * 100) if unique_opens > 0 else 0
        
        return {
            'campaign_id': campaign_id,
            'total_sent': total_sent,
            'unique_opens': unique_opens,
            'total_opens': total_opens,
            'unique_clicks': unique_clicks,
            'total_clicks': total_clicks,
            'open_rate': round(open_rate, 2),
            'click_rate': round(click_rate, 2),
            'click_to_open_rate': round(click_to_open_rate, 2),
            'recent_opens': recent_opens,
            'recent_clicks': recent_clicks,
            'last_updated': datetime.now().isoformat(),
            'is_active': recent_opens > 0 or recent_clicks > 0,
            'recipients': recipient_details
        }
    except Exception as e:
        print(f"❌ Analytics error: {str(e)}")
        return None

def save_analytics_snapshot(campaign_id, analytics):
    """Save analytics snapshot to database"""
    try:
        conn = sqlite3.connect('real_tracking.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO analytics_snapshots 
            (campaign_id, total_sent, unique_opens, total_opens, unique_clicks, 
             total_clicks, open_rate, click_rate) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            campaign_id, analytics['total_sent'], analytics['unique_opens'],
            analytics['total_opens'], analytics['unique_clicks'], analytics['total_clicks'],
            analytics['open_rate'], analytics['click_rate']
        ))
        
        conn.commit()
        conn.close()
        print(f"📊 Analytics snapshot saved for campaign {campaign_id}")
    except Exception as e:
        print(f"❌ Error saving snapshot: {str(e)}")

def tracking_loop():
    """Main tracking loop - runs every 2 minutes"""
    print("🚀 Starting 2-minute real-time tracking loop...")
    
    while True:
        try:
            print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] Running real-time analytics update...")
            
            # Get current analytics
            analytics = get_campaign_analytics(TEST_CAMPAIGN_ID)
            
            if analytics:
                # Save snapshot
                save_analytics_snapshot(TEST_CAMPAIGN_ID, analytics)
                
                # Emit real-time update via WebSocket
                socketio.emit('campaign_update', {
                    'campaign_id': TEST_CAMPAIGN_ID,
                    'campaign_name': 'Real Email Tracking Test',
                    'analytics': analytics,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Print detailed analytics to console
                print(f"📈 Campaign {TEST_CAMPAIGN_ID} Real-Time Analytics:")
                print(f"   📧 Total Sent: {analytics['total_sent']}")
                print(f"   👀 Unique Opens: {analytics['unique_opens']} ({analytics['open_rate']}%)")
                print(f"   🔄 Total Opens: {analytics['total_opens']}")
                print(f"   🖱️  Unique Clicks: {analytics['unique_clicks']} ({analytics['click_rate']}%)")
                print(f"   🔄 Total Clicks: {analytics['total_clicks']}")
                print(f"   🔥 Recent Activity (2min): {analytics['recent_opens']} opens, {analytics['recent_clicks']} clicks")
                
                # Print recipient details
                print("   📋 Recipient Status:")
                for recipient in analytics['recipients']:
                    status_emoji = "✅" if recipient['opens'] > 0 else "📫"
                    print(f"      {status_emoji} {recipient['email']}: {recipient['opens']} opens, {recipient['clicks']} clicks")
                
                # Check for significant recent activity
                if analytics['recent_opens'] > 0 or analytics['recent_clicks'] > 0:
                    alert_message = f"🚨 REAL-TIME ACTIVITY! {analytics['recent_opens']} opens, {analytics['recent_clicks']} clicks in last 2 minutes"
                    print(f"   {alert_message}")
                    
                    # Emit activity alert
                    socketio.emit('activity_alert', {
                        'campaign_id': TEST_CAMPAIGN_ID,
                        'campaign_name': 'Real Email Tracking Test',
                        'recent_opens': analytics['recent_opens'],
                        'recent_clicks': analytics['recent_clicks'],
                        'message': alert_message
                    })
            else:
                print("❌ No analytics data available")
            
        except Exception as e:
            print(f"❌ Tracking loop error: {str(e)}")
        
        # Wait 2 minutes (120 seconds)
        print("⏳ Waiting 2 minutes for next real-time update...")
        time.sleep(120)

# Tracking Routes
@app.route('/track/open/<tracking_id>')
def track_open(tracking_id):
    """Track email opens"""
    try:
        conn = sqlite3.connect('real_tracking.db')
        cursor = conn.cursor()
        
        # Check if tracking_id exists
        cursor.execute('SELECT email FROM recipients WHERE tracking_id = ?', (tracking_id,))
        recipient = cursor.fetchone()
        
        if recipient:
            cursor.execute(
                'INSERT INTO email_opens (tracking_id, ip_address, user_agent) VALUES (?, ?, ?)',
                (tracking_id, request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr), 
                 request.headers.get('User-Agent', ''))
            )
            conn.commit()
            print(f"📧 EMAIL OPENED! {recipient[0]} - tracking_id: {tracking_id}")
            
            # Emit real-time open event
            socketio.emit('email_opened', {
                'tracking_id': tracking_id,
                'email': recipient[0],
                'timestamp': datetime.now().isoformat()
            })
        
        conn.close()
        
        # Return 1x1 transparent pixel
        pixel_data = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
        return send_file(
            io.BytesIO(pixel_data),
            mimetype='image/gif',
            as_attachment=False
        )
    except Exception as e:
        print(f"❌ Error tracking open: {str(e)}")
        pixel_data = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
        return send_file(io.BytesIO(pixel_data), mimetype='image/gif')

@app.route('/track/click/<tracking_id>/<path:encoded_url>')
def track_click(tracking_id, encoded_url):
    """Track link clicks"""
    try:
        original_url = unquote(encoded_url)
        
        conn = sqlite3.connect('real_tracking.db')
        cursor = conn.cursor()
        
        # Check if tracking_id exists
        cursor.execute('SELECT email FROM recipients WHERE tracking_id = ?', (tracking_id,))
        recipient = cursor.fetchone()
        
        if recipient:
            cursor.execute(
                'INSERT INTO link_clicks (tracking_id, url, ip_address, user_agent) VALUES (?, ?, ?, ?)',
                (tracking_id, original_url, request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
                 request.headers.get('User-Agent', ''))
            )
            conn.commit()
            print(f"🖱️  LINK CLICKED! {recipient[0]} clicked: {original_url} - tracking_id: {tracking_id}")
            
            # Emit real-time click event
            socketio.emit('link_clicked', {
                'tracking_id': tracking_id,
                'email': recipient[0],
                'url': original_url,
                'timestamp': datetime.now().isoformat()
            })
        
        conn.close()
        
        # Redirect to original URL
        return redirect(original_url, code=302)
        
    except Exception as e:
        print(f"❌ Error tracking click: {str(e)}")
        return f"Error: {str(e)}", 500

# API Endpoints
@app.route('/api/send-campaign')
def send_campaign():
    """Send campaign to real email addresses"""
    try:
        conn = sqlite3.connect('real_tracking.db')
        cursor = conn.cursor()
        
        # Get campaign details
        cursor.execute('SELECT * FROM campaigns WHERE id = ?', (TEST_CAMPAIGN_ID,))
        campaign = cursor.fetchone()
        
        if not campaign:
            return jsonify({'error': 'Campaign not found'}), 404
        
        _, name, subject, content, status, created_at, sent_at = campaign
        
        # Clear existing recipients for this campaign
        cursor.execute('DELETE FROM recipients WHERE campaign_id = ?', (TEST_CAMPAIGN_ID,))
        cursor.execute('DELETE FROM email_opens WHERE tracking_id IN (SELECT tracking_id FROM recipients WHERE campaign_id = ?)', (TEST_CAMPAIGN_ID,))
        cursor.execute('DELETE FROM link_clicks WHERE tracking_id IN (SELECT tracking_id FROM recipients WHERE campaign_id = ?)', (TEST_CAMPAIGN_ID,))
        
        sent_emails = []
        
        print(f"🚀 Starting to send campaign to {len(REAL_EMAIL_ADDRESSES)} real recipients...")
        
        for email in REAL_EMAIL_ADDRESSES:
            tracking_id = generate_tracking_id()
            
            # Insert recipient record
            cursor.execute(
                'INSERT INTO recipients (campaign_id, email, tracking_id, delivery_status) VALUES (?, ?, ?, ?)',
                (TEST_CAMPAIGN_ID, email, tracking_id, 'sending')
            )
            
            # Add link tracking
            tracked_content = add_link_tracking(content, tracking_id)
            
            # Send real email
            if send_real_email(email, subject, tracked_content):
                cursor.execute(
                    'UPDATE recipients SET delivery_status = ? WHERE tracking_id = ?',
                    ('sent', tracking_id)
                )
                sent_emails.append({
                    'email': email, 
                    'tracking_id': tracking_id,
                    'status': 'sent'
                })
            else:
                cursor.execute(
                    'UPDATE recipients SET delivery_status = ? WHERE tracking_id = ?',
                    ('failed', tracking_id)
                )
                sent_emails.append({
                    'email': email, 
                    'tracking_id': tracking_id,
                    'status': 'failed'
                })
        
        # Update campaign status
        cursor.execute('UPDATE campaigns SET status = ?, sent_at = ? WHERE id = ?', 
                      ('sent', datetime.now().isoformat(), TEST_CAMPAIGN_ID))
        
        conn.commit()
        conn.close()
        
        successful_sends = len([e for e in sent_emails if e['status'] == 'sent'])
        
        return jsonify({
            'success': True,
            'message': f'Campaign sent! {successful_sends}/{len(REAL_EMAIL_ADDRESSES)} emails delivered',
            'campaign_id': TEST_CAMPAIGN_ID,
            'campaign_name': name,
            'sent_details': sent_emails,
            'tracking_url': f'{BASE_URL}/api/analytics/current'
        })
        
    except Exception as e:
        print(f"❌ Error sending campaign: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/current')
def get_current_analytics():
    """Get current analytics for test campaign"""
    analytics = get_campaign_analytics(TEST_CAMPAIGN_ID)
    if analytics:
        return jsonify({
            'success': True,
            'analytics': analytics,
            'instructions': {
                'email_tracking': 'Open any sent email to register an open event',
                'click_tracking': 'Click any link in the email to register a click event',
                'real_time_updates': 'Analytics update every 2 minutes automatically'
            }
        })
    return jsonify({'error': 'No campaign data available. Send campaign first.'}), 404

@app.route('/api/status')
def api_status():
    """System status"""
    return jsonify({
        'status': 'running',
        'timestamp': datetime.now().isoformat(),
        'campaign_id': TEST_CAMPAIGN_ID,
        'real_emails': REAL_EMAIL_ADDRESSES,
        'tracking_interval': '2 minutes',
        'base_url': BASE_URL,
        'endpoints': [
            'GET /api/send-campaign - Send emails to real addresses',
            'GET /api/analytics/current - Get real-time analytics',
            'GET /api/status - System status'
        ]
    })

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    print('🔌 Client connected to real-time tracking')
    emit('connected', {
        'message': 'Connected to real email tracking system',
        'campaign_id': TEST_CAMPAIGN_ID
    })

if __name__ == '__main__':
    # Initialize database
    init_tracking_db()
    
    # Start tracking thread
    tracking_thread = threading.Thread(target=tracking_loop, daemon=True)
    tracking_thread.start()
    
    print("="*70)
    print("📧 REAL EMAIL CAMPAIGN TRACKING SYSTEM")
    print("="*70)
    print(f"🎯 Campaign ID: {TEST_CAMPAIGN_ID}")
    print(f"📬 Real Email Addresses:")
    for email in REAL_EMAIL_ADDRESSES:
        print(f"   • {email}")
    print(f"🌐 Base URL: {BASE_URL}")
    print("⏰ Real-time Analytics: Every 2 minutes")
    print("🔄 WebSocket Updates: Enabled")
    print("="*70)
    print("🚀 SETUP REQUIRED:")
    print(f"   1. Update SENDER_EMAIL and SENDER_PASSWORD in the code")
    print(f"   2. Update BASE_URL to your actual domain")
    print(f"   3. Visit: {BASE_URL}/api/send-campaign to send emails")
    print(f"   4. Monitor: {BASE_URL}/api/analytics/current for live stats")
    print("="*70)
    
    # Run the Flask-SocketIO app
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)