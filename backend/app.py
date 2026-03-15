from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import json
import os
import threading
from model import ProductivityModel
from db import DatabaseManager
from langchain_core.prompts import PromptTemplate
from brain import analyze_user_mental_health
from checkUrl import analyze_url

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Thread-local storage for database connections
local_data = threading.local()

def get_db_manager():
    """Get thread-local database manager"""
    if not hasattr(local_data, 'db_manager'):
        local_data.db_manager = DatabaseManager()
        local_data.db_manager.initialize_database()
    return local_data.db_manager

def get_model():
    """Get thread-local model"""
    if not hasattr(local_data, 'model'):
        local_data.model = ProductivityModel()
    return local_data.model

@app.route('/api/distraction-urls', methods=['POST', 'OPTIONS'])
def handle_distraction_urls():
    """Handle distraction URLs from extension"""
    try:
        data = get_request_data()
        print(f"Received data: {data}")
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
            
        urls = data.get('urls', [])
        user_id = data.get('user_id', 'default_user')
        
        # Validate URLs
        if not isinstance(urls, list):
            return jsonify({
                'status': 'error',
                'message': 'URLs must be a list'
            }), 400
        
        # Get thread-local instances
        db_manager = get_db_manager()
        model = get_model()
        
        # Store in database
        db_manager.store_distraction_urls(user_id, urls)
        
        # Update model with new data
        model.update_distraction_patterns(user_id, [{'url': url} for url in urls])
        
        return jsonify({
            'status': 'success',
            'message': 'Distraction URLs updated',
            'count': len(urls)
        })
    
    except Exception as e:
        print(f"Error in handle_distraction_urls: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/productive-urls', methods=['POST', 'OPTIONS'])
def handle_productive_urls():
    """Handle productive URLs from extension"""
    try:
        data = get_request_data()
        print(f"Received data: {data}")
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
            
        urls = data.get('urls', [])
        user_id = data.get('user_id', 'default_user')
        
        # Validate URLs
        if not isinstance(urls, list):
            return jsonify({
                'status': 'error',
                'message': 'URLs must be a list'
            }), 400
        
        # Get thread-local instances
        db_manager = get_db_manager()
        model = get_model()
        
        # Store in database
        db_manager.store_productive_urls(user_id, urls)
        
        # Update model with new data
        model.update_productive_patterns(user_id, [{'url': url} for url in urls])
        
        return jsonify({
            'status': 'success',
            'message': 'Productive URLs updated',
            'count': len(urls)
        })
    
    except Exception as e:
        print(f"Error in handle_productive_urls: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/behavior-upload', methods=['POST'])
def behavior_upload():
    data = request.get_json()
    if not data or 'behavior' not in data:
        return jsonify({"error": "Invalid payload"}), 400
    
    # Save uploaded data to file
    json_path = "latest_behavior_upload.json"
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)

    try:
        # Pass the saved JSON into the brain for analysis
        with open(json_path, "r") as f:
            session_json = f.read()
            # print(f"Session JSON: {session_json}")
        analysis_result = analyze_user_mental_health(session_json)
        # print(f"Analysis Result: {analysis_result}")
        return jsonify({
            "status": "uploaded_and_analyzed",
            "analysis": analysis_result
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500



@app.route('/api/usage-data', methods=['POST', 'OPTIONS'])
def handle_usage_data():
    """Handle usage data from extension"""
    try:
        data = get_request_data()
        print(f"Received data: {data}")
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
            
        user_id = data.get('user_id', 'default_user')
        
        # Validate required fields
        required_fields = ['url', 'domain', 'duration']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Get thread-local instances
        db_manager = get_db_manager()
        model = get_model()
        
        # Store usage data
        usage_entry = {
            'user_id': user_id,
            'url': data.get('url'),
            'domain': data.get('domain'),
            'duration': int(data.get('duration', 0)),
            'interactions': data.get('interactions', {}),
            'timestamp': data.get('timestamp', datetime.now().isoformat()),
            'is_distraction': bool(data.get('is_distraction', data.get('isDistraction', False))),
            'is_productive': bool(data.get('is_productive', data.get('isProductive', False)))
        }
        
        db_manager.store_usage_data(usage_entry)
        
        # Update model with usage patterns
        model.process_usage_data(usage_entry)
        
        return jsonify({
            'status': 'success',
            'message': 'Usage data recorded'
        })
    
    except Exception as e:
        print(f"Error in handle_usage_data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/tab-activity', methods=['POST', 'OPTIONS'])
def handle_tab_activity():
    """Handle tab activity data"""
    try:
        data = get_request_data()
        print(f"Received data: {data}")
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
            
        user_id = data.get('user_id', 'default_user')
        
        # Get thread-local instances
        db_manager = get_db_manager()
        model = get_model()
        
        tab_data = {
            'user_id': user_id,
            'url': data.get('url', ''),
            'title': data.get('title', ''),
            'timestamp': data.get('timestamp', datetime.now().isoformat()),
            'time_of_day': int(data.get('timeOfDay', datetime.now().hour))
        }
        
        # Store tab activity
        db_manager.store_tab_activity(tab_data)
        
        # Analyze the URL and print response
        url = tab_data['url']
        if url:
            try:
                print(f"\n--- Analyzing URL: {url} ---")
                url_analysis = analyze_url(url)
                print(f"URL Analysis Response:")
                print(json.dumps(url_analysis, indent=2))
                print(f"--- End URL Analysis ---\n")
                
                # Optionally log specific parts
                if url_analysis.get('thought'):
                    print(f"Thought: {url_analysis['thought']}")
                if url_analysis.get('action_input'):
                    print(f"Action Input: {url_analysis['action_input']}")
                    
            except Exception as e:
                print(f"Error analyzing URL {url}: {str(e)}")
        else:
            print("No URL provided for analysis")
        
        # Analyze tab activity for patterns
        should_alert = model.analyze_tab_activity(tab_data)
        
        response = {'status': 'success'}
        if should_alert:
            response['alert'] = should_alert
        
        return jsonify(response)
    
    except Exception as e:
        print(f"Error in handle_tab_activity: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }), 500


@app.route('/api/get-question', methods=['POST', 'OPTIONS'])
def get_question():
    """Get AI-generated question for user when they exceed limits"""
    try:
        data = get_request_data()
        print(f"Received data: {data}")
        
        if not data:
            return jsonify({
                'question': 'You have exceeded your time limit. Do you want to continue?',
                'domain': 'unknown',
                'timestamp': datetime.now().isoformat()
            })
            
        domain = data.get('domain', 'unknown')
        excess_time = int(data.get('excessTime', 0))
        user_id = data.get('user_id', 'default_user')
        
        # Get thread-local instances
        db_manager = get_db_manager()
        model = get_model()
        
        # Get user's context and history
        user_context = db_manager.get_user_context(user_id)
        
        # Generate personalized question using AI model
        question = model.generate_intervention_question(
            domain=domain,
            excess_time=excess_time,
            user_context=user_context
        )
        
        return jsonify({
            'question': question,
            'domain': domain,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        print(f"Error in get_question: {str(e)}")
        return jsonify({
            'question': 'You have exceeded your time limit. Do you want to continue?',
            'domain': data.get('domain', 'unknown') if data else 'unknown',
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/question-answer', methods=['POST', 'OPTIONS'])
def handle_question_answer():
    """Handle user's answer to intervention question"""
    try:
        data = get_request_data()
        print(f"Received data: {data}")
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
            
        answer = data.get('answer', '')
        domain = data.get('domain', 'unknown')
        user_id = data.get('user_id', 'default_user')
        timestamp = data.get('timestamp', datetime.now().isoformat())
        
        # Get thread-local instances
        db_manager = get_db_manager()
        model = get_model()
        
        # Store the interaction
        interaction = {
            'user_id': user_id,
            'domain': domain,
            'answer': answer,
            'timestamp': timestamp
        }
        
        db_manager.store_intervention_response(interaction)
        
        # Process the answer and determine rewards/penalties
        result = model.process_intervention_response(interaction)
        
        response = {
            'status': 'success',
            'message': 'Response recorded'
        }
        
        # Add reward points if applicable
        if result.get('reward_points'):
            response['rewardPoints'] = result['reward_points']
        
        # Add updated time limits if applicable
        if result.get('updated_limits'):
            response['updatedLimits'] = result['updated_limits']
        
        return jsonify(response)
    
    except Exception as e:
        print(f"Error in handle_question_answer: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/get-insights', methods=['GET'])
def get_insights():
    """Get AI-generated insights about user's productivity patterns"""
    try:
        user_id = request.args.get('user_id', 'default_user')
        
        # Get thread-local instances
        db_manager = get_db_manager()
        model = get_model()
        
        # Get user data
        user_data = db_manager.get_user_analytics_data(user_id)
        
        # Generate insights using AI model
        insights = model.generate_productivity_insights(user_data)
        
        return jsonify({
            'insights': insights,
            'generated_at': datetime.now().isoformat()
        })
    
    except Exception as e:
        print(f"Error in get_insights: {str(e)}")
        return jsonify({
            'insights': ['Unable to generate insights at this time'],
            'error': str(e),
            'generated_at': datetime.now().isoformat()
        }), 500

@app.route('/api/adjust-limits', methods=['POST', 'OPTIONS'])
def adjust_limits():
    """Adjust time limits based on AI recommendations"""
    try:
        data = get_request_data()
        print(f"Received data: {data}")
        user_id = data.get('user_id', 'default_user') if data else 'default_user'
        
        # Get thread-local instances
        db_manager = get_db_manager()
        model = get_model()
        
        # Get current user performance
        performance_data = db_manager.get_user_performance(user_id)
        
        # Get AI recommendations for limit adjustments
        recommendations = model.recommend_limit_adjustments(performance_data)
        
        # Update limits in database
        if recommendations.get('distraction_adjustments'):
            db_manager.update_distraction_limits(user_id, recommendations['distraction_adjustments'])
        
        if recommendations.get('productive_adjustments'):
            db_manager.update_productive_targets(user_id, recommendations['productive_adjustments'])
        
        return jsonify({
            'status': 'success',
            'recommendations': recommendations,
            'applied_at': datetime.now().isoformat()
        })
    
    except Exception as e:
        print(f"Error in adjust_limits: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }), 500

@app.route('/api/daily-summary', methods=['GET'])
def get_daily_summary():
    """Get daily productivity summary"""
    try:
        user_id = request.args.get('user_id', 'default_user')
        date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # Get thread-local instances
        db_manager = get_db_manager()
        model = get_model()
        
        # Get daily data
        daily_data = db_manager.get_daily_data(user_id, date)
        
        # Generate summary using AI
        summary = model.generate_daily_summary(daily_data)
        
        return jsonify({
            'summary': summary,
            'date': date,
            'generated_at': datetime.now().isoformat()
        })
    
    except Exception as e:
        print(f"Error in get_daily_summary: {str(e)}")
        return jsonify({
            'summary': {
                'total_productive_time': 0,
                'total_distraction_time': 0,
                'key_insights': ['Unable to generate summary at this time']
            },
            'error': str(e),
            'date': request.args.get('date', datetime.now().strftime('%Y-%m-%d')),
            'generated_at': datetime.now().isoformat()
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db_manager = get_db_manager()
        conn = db_manager._get_connection()
        conn.execute('SELECT 1')
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'database': 'connected'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'version': '1.0.0',
            'database': 'disconnected',
            'error': str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'status': 'error',
        'message': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    print(f"Internal server error: {str(error)}")
    return jsonify({
        'status': 'error',
        'message': 'Internal server error'
    }), 500

@app.before_request
def handle_preflight():
    """Handle CORS preflight requests and log incoming requests"""
    print(f"Request: {request.method} {request.path}")
    print(f"Content-Type: {request.content_type}")
    print(f"Headers: {dict(request.headers)}")
    
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
        response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
        return response

def get_request_data():
    """Helper function to get request data regardless of content type"""
    try:
        # Try to get JSON data first
        if request.is_json:
            return request.get_json()
        
        # If content-type is not set properly but data looks like JSON
        if request.data:
            import json
            try:
                return json.loads(request.data.decode('utf-8'))
            except:
                pass
        
        # Try form data
        if request.form:
            return request.form.to_dict()
        
        # Try args for GET requests
        if request.args:
            return request.args.to_dict()
            
        return None
    except Exception as e:
        print(f"Error getting request data: {e}")
        return None

if __name__ == '__main__':
    # Initialize database once at startup
    try:
        initial_db = DatabaseManager()
        initial_db.initialize_database()
        initial_db.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")
    
    # Start the server
    print("Starting Flask server...")
    app.run(
        host='localhost',
        port=5000,
        debug=True,
        threaded=True
    )
