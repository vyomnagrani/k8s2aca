from flask import Flask, render_template, request, send_file, flash, redirect, url_for, jsonify
import os
import tempfile
import yaml
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import logging
from datetime import datetime
import uuid

import secrets

# Import the existing conversion logic
from main import convert_k8s_to_aca

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Generate a secure secret key if none provided
def get_secret_key():
    """Generate or retrieve a secure secret key."""
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        # Generate a secure random key for this session
        secret_key = secrets.token_hex(32)
        logger.info("Generated new secret key for this session")
    return secret_key

app.secret_key = get_secret_key()
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Allowed file extensions
ALLOWED_EXTENSIONS = {'yaml', 'yml'}

def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_k8s_manifest(file_path):
    """Validate that the uploaded file is a valid Kubernetes manifest."""
    try:
        with open(file_path, 'r') as f:
            documents = list(yaml.safe_load_all(f))
            
        # Check if at least one document exists
        if not documents or len(documents) == 0:
            return False, "File is empty or contains no valid YAML documents"
        
        # Check for at least one Kubernetes resource
        valid_kinds = {'Deployment', 'Service', 'Ingress', 'ConfigMap', 'Secret', 'Pod', 'ReplicaSet'}
        found_k8s_resource = False
        
        for doc in documents:
            if isinstance(doc, dict) and doc.get('kind') in valid_kinds:
                found_k8s_resource = True
                break
        
        if not found_k8s_resource:
            return False, "No valid Kubernetes resources found in the file"
            
        return True, "Valid Kubernetes manifest"
        
    except yaml.YAMLError as e:
        return False, f"Invalid YAML format: {str(e)}"
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

@app.route('/')
def index():
    """Main page with file upload form."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and conversion."""
    try:
        # Check if file was uploaded
        if 'k8s_file' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(url_for('index'))
        
        file = request.files['k8s_file']
        
        # Check if file was selected
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('index'))
        
        # Check file extension
        if not allowed_file(file.filename):
            flash('Invalid file type. Please upload a YAML file (.yaml or .yml)', 'error')
            return redirect(url_for('index'))
        
        # Generate unique filename to avoid conflicts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        filename = secure_filename(file.filename)
        base_name = os.path.splitext(filename)[0]
        
        # Save uploaded file
        input_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_{timestamp}_{unique_id}.yaml")
        file.save(input_file)
        
        # Validate the uploaded file
        is_valid, message = validate_k8s_manifest(input_file)
        if not is_valid:
            os.remove(input_file)  # Clean up
            flash(f'Invalid Kubernetes manifest: {message}', 'error')
            return redirect(url_for('index'))
        
        # Generate output filenames
        output_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_aca_{timestamp}_{unique_id}.yaml")
        
        # Convert the file
        try:
            convert_k8s_to_aca(input_file, output_file)
            
            # Read the migration report
            report_file = output_file.replace('.yaml', '.migration.txt')
            migration_report = ""
            if os.path.exists(report_file):
                with open(report_file, 'r') as f:
                    migration_report = f.read()
            
            # Read the generated ACA template
            aca_template = ""
            if os.path.exists(output_file):
                with open(output_file, 'r') as f:
                    aca_template = f.read()
            
            # Clean up input file
            os.remove(input_file)
            
            # Store file paths in session or pass them to template
            return render_template('results.html', 
                                 aca_template=aca_template,
                                 migration_report=migration_report,
                                 output_file=os.path.basename(output_file),
                                 report_file=os.path.basename(report_file) if os.path.exists(report_file) else None,
                                 original_filename=filename)
            
        except Exception as e:
            # Clean up files on error
            if os.path.exists(input_file):
                os.remove(input_file)
            if os.path.exists(output_file):
                os.remove(output_file)
            
            logger.error(f"Conversion error: {str(e)}")
            flash(f'Error during conversion: {str(e)}', 'error')
            return redirect(url_for('index'))
            
    except RequestEntityTooLarge:
        flash('File too large. Maximum size is 16MB.', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        flash(f'Error processing upload: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    """Download generated files."""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Security check: ensure the file exists and is in the upload folder
        if not os.path.exists(file_path) or not file_path.startswith(app.config['UPLOAD_FOLDER']):
            flash('File not found', 'error')
            return redirect(url_for('index'))
        
        # Determine the appropriate MIME type
        if filename.endswith('.yaml') or filename.endswith('.yml'):
            mimetype = 'application/x-yaml'
        else:
            mimetype = 'text/plain'
        
        return send_file(file_path, as_attachment=True, download_name=filename, mimetype=mimetype)
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        flash(f'Error downloading file: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/convert', methods=['POST'])
def api_convert():
    """API endpoint for programmatic conversion."""
    try:
        # Check if file was uploaded
        if 'k8s_file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['k8s_file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please upload a YAML file'}), 400
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        filename = secure_filename(file.filename)
        base_name = os.path.splitext(filename)[0]
        
        # Save and process file
        input_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_{timestamp}_{unique_id}.yaml")
        output_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{base_name}_aca_{timestamp}_{unique_id}.yaml")
        
        file.save(input_file)
        
        # Validate file
        is_valid, message = validate_k8s_manifest(input_file)
        if not is_valid:
            os.remove(input_file)
            return jsonify({'error': f'Invalid Kubernetes manifest: {message}'}), 400
        
        # Convert
        convert_k8s_to_aca(input_file, output_file)
        
        # Read results
        aca_template = ""
        migration_report = ""
        
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                aca_template = f.read()
        
        report_file = output_file.replace('.yaml', '.migration.txt')
        if os.path.exists(report_file):
            with open(report_file, 'r') as f:
                migration_report = f.read()
        
        # Clean up
        os.remove(input_file)
        if os.path.exists(output_file):
            os.remove(output_file)
        if os.path.exists(report_file):
            os.remove(report_file)
        
        return jsonify({
            'aca_template': aca_template,
            'migration_report': migration_report,
            'success': True
        })
        
    except Exception as e:
        logger.error(f"API conversion error: {str(e)}")
        return jsonify({'error': f'Conversion failed: {str(e)}'}), 500

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    """Handle file too large error."""
    flash('File too large. Maximum size is 16MB.', 'error')
    return redirect(url_for('index'))

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {str(e)}")
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # Use environment variables for production configuration
    flask_env = os.environ.get('FLASK_ENV', 'production')
    debug_mode = flask_env.lower() in ['development', 'dev', 'debug']
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    
    logger.info(f"Starting Flask app in {flask_env} mode on {host}:{port}")
    app.run(debug=debug_mode, host=host, port=port)
