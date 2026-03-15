import os
import json
import sqlite3
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dotenv import load_dotenv

# Corrected imports for Mistral
from langchain_mistralai import ChatMistralAI
from langchain.agents import AgentExecutor
from langchain.tools import Tool
from langchain.agents.format_scratchpad import format_log_to_str
from langchain.agents.output_parsers import JSONAgentOutputParser
from langchain.tools.render import render_text_description_and_args
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

load_dotenv()

# Configuration
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Initialize Mistral AI (Lines 19-25)
llm = ChatMistralAI(
    model="mistral-large-latest",
    api_key=MISTRAL_API_KEY,
    temperature=0.4,
    max_tokens=500
)

class UserDataProcessor:
    """Process and prepare user behavioral data for mental health analysis"""
    
    def __init__(self):
        self.db_path = "user_behavior_history.db"
        self.init_database()
        
        # Mental health indicators based on research
        self.stress_indicators = {
            'excessive_tab_switching': {'threshold': 100, 'weight': 0.3},
            'short_session_duration': {'threshold': 30, 'weight': 0.2},
            'late_night_activity': {'threshold': 23, 'weight': 0.25},
            'repetitive_behavior': {'threshold': 0.7, 'weight': 0.15},
            'decreased_typing_speed': {'threshold': -20, 'weight': 0.1}
        }
        
        self.productivity_sites = [
            'github.com', 'stackoverflow.com', 'docs.', 'learn.', 'education',
            'coursera.com', 'udemy.com', 'khan', 'wikipedia.org', 'medium.com'
        ]
        
        self.distraction_sites = [
            'facebook.com', 'instagram.com', 'twitter.com', 'tiktok.com',
            'youtube.com', 'netflix.com', 'reddit.com', 'gaming', 'entertainment'
        ]

    def init_database(self):
        """Initialize SQLite database for storing historical data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                session_data TEXT,
                mental_health_score REAL,
                intervention_triggered INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default',
                avg_session_time REAL,
                avg_tab_switches REAL,
                productivity_ratio REAL,
                stress_baseline REAL,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    def store_session_data(self, session_data: dict, mental_health_score: float, intervention: bool):
        """Store session data in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_sessions (timestamp, session_data, mental_health_score, intervention_triggered)
            VALUES (?, ?, ?, ?)
        ''', (
            session_data.get('sessionData', {}).get('timestamp', datetime.now().isoformat()),
            json.dumps(session_data),
            mental_health_score,
            1 if intervention else 0
        ))
        
        conn.commit()
        conn.close()

    def get_historical_data(self, days: int = 30) -> list[dict]:
        """Retrieve historical session data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        cursor.execute('''
            SELECT session_data, mental_health_score, intervention_triggered, created_at
            FROM user_sessions
            WHERE created_at > ?
            ORDER BY created_at DESC
        ''', (cutoff_date,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'session_data': json.loads(row[0]),
                'mental_health_score': row[1],
                'intervention_triggered': bool(row[2]),
                'timestamp': row[3]
            }
            for row in results
        ]

    def extract_behavioral_features(self, session_data: Dict) -> Dict:
        """Extract behavioral features from session data"""
        features = {}
        
        # Session metadata
        session_info = session_data.get('sessionData', {})
        features['session_duration'] = session_info.get('sessionTime', 0) / 60  # Convert to minutes
        features['tab_switch_count'] = session_info.get('tabSwitchCount', 0)
        features['tab_switch_rate'] = features['tab_switch_count'] / max(features['session_duration'], 1)
        
        # Time analysis
        timestamp = session_info.get('timestamp', datetime.now().isoformat())
        try:
            session_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            features['hour_of_day'] = session_time.hour
            features['is_late_night'] = 1 if session_time.hour >= 23 or session_time.hour <= 5 else 0
        except:
            features['hour_of_day'] = 12
            features['is_late_night'] = 0
        
        # URL analysis
        visit_freq = session_data.get('visitFrequency', {})
        behavior_data = session_data.get('behaviorData', {})
        url_time = session_data.get('urlTimeSpent', {})
        
        total_sites = len(visit_freq)
        productive_sites = 0
        distraction_sites = 0
        
        for site in visit_freq.keys():
            if any(prod in site.lower() for prod in self.productivity_sites):
                productive_sites += 1
            elif any(dist in site.lower() for dist in self.distraction_sites):
                distraction_sites += 1
        
        features['total_sites_visited'] = total_sites
        features['productivity_ratio'] = productive_sites / max(total_sites, 1)
        features['distraction_ratio'] = distraction_sites / max(total_sites, 1)
        
        # Behavioral patterns
        total_clicks = sum(data[0].get('clicks', 0) for data in behavior_data.values() if data)
        total_scrolls = sum(data[0].get('scrolls', 0) for data in behavior_data.values() if data)
        total_keystrokes = sum(data[0].get('keystrokes', 0) for data in behavior_data.values() if data)
        
        features['total_interactions'] = total_clicks + total_scrolls + total_keystrokes
        features['interaction_rate'] = features['total_interactions'] / max(features['session_duration'], 1)
        
        # Typing speed analysis
        typing_speeds = []
        for site_data in behavior_data.values():
            if site_data and len(site_data) > 0:
                typing_data = site_data[0].get('typingSpeed', {})
                sessions = typing_data.get('sessions', [])
                for session in sessions:
                    if session.get('wpm', 0) > 0:
                        typing_speeds.append(session['wpm'])
        
        features['avg_typing_speed'] = np.mean(typing_speeds) if typing_speeds else 0
        features['typing_consistency'] = 1 - (np.std(typing_speeds) / max(np.mean(typing_speeds), 1)) if len(typing_speeds) > 1 else 1
        
        # Site switching patterns
        features['site_diversity'] = len(set(visit_freq.keys()))
        features['repetitive_behavior'] = max(visit_freq.values()) / sum(visit_freq.values()) if visit_freq else 0
        
        return features

    def calculate_stress_indicators(self, features: Dict, historical_data: List[Dict]) -> Dict:
        """Calculate stress indicators based on current and historical data"""
        stress_scores = {}
        
        # Excessive tab switching
        tab_switch_rate = features.get('tab_switch_rate', 0)
        historical_tab_rates = [self.extract_behavioral_features(h['session_data']).get('tab_switch_rate', 0) 
                                for h in historical_data[-10:]]  # Last 10 sessions
        baseline_tab_rate = np.mean(historical_tab_rates) if historical_tab_rates else 5
        
        stress_scores['excessive_tab_switching'] = min(1.0, max(0, 
            (tab_switch_rate - baseline_tab_rate) / max(baseline_tab_rate, 1)))
        
        # Short session duration with high activity
        session_duration = features.get('session_duration', 0)
        interaction_rate = features.get('interaction_rate', 0)
        if session_duration < 30 and interaction_rate > 10:  # Short but intense sessions
            stress_scores['short_intense_sessions'] = 1.0
        else:
            stress_scores['short_intense_sessions'] = 0.0
        
        # Late night activity
        stress_scores['late_night_activity'] = features.get('is_late_night', 0)
        
        # Repetitive behavior (obsessive site visiting)
        stress_scores['repetitive_behavior'] = features.get('repetitive_behavior', 0)
        
        # Decreased productivity
        current_productivity = features.get('productivity_ratio', 0)
        historical_productivity = [self.extract_behavioral_features(h['session_data']).get('productivity_ratio', 0) 
                                   for h in historical_data[-10:]]
        baseline_productivity = np.mean(historical_productivity) if historical_productivity else 0.3
        
        productivity_decline = max(0, (baseline_productivity - current_productivity) / max(baseline_productivity, 0.1))
        stress_scores['productivity_decline'] = min(1.0, productivity_decline)
        
        # Typing speed variance (sign of stress/fatigue)
        typing_consistency = features.get('typing_consistency', 1)
        stress_scores['typing_inconsistency'] = 1 - typing_consistency
        
        return stress_scores

class MentalHealthAnalyzer:
    """Main class for analyzing mental health based on user behavior"""
    
    def __init__(self):
        self.data_processor = UserDataProcessor()
        self.last_intervention_time = None
        self.intervention_cooldown = timedelta(hours=2)  # Minimum 2 hours between interventions
        
    def analyze_mental_state(self, session_data: Dict) -> Dict:
        """Analyze current mental state and return intervention recommendation"""
        
        # Extract behavioral features
        current_features = self.data_processor.extract_behavioral_features(session_data)
        
        # Get historical data for context
        historical_data = self.data_processor.get_historical_data(days=30)
        
        # Calculate stress indicators
        stress_indicators = self.data_processor.calculate_stress_indicators(current_features, historical_data)
        
        # Calculate overall mental health score (0-1, where 1 is high stress/poor mental health)
        mental_health_score = self._calculate_mental_health_score(stress_indicators, current_features)
        
        # Determine intervention type
        intervention_type = self._determine_intervention(mental_health_score, stress_indicators)
        
        # Store data for future analysis
        self.data_processor.store_session_data(
            session_data, 
            mental_health_score, 
            intervention_type != 'none'
        )
        
        return {
            'mental_health_score': mental_health_score,
            'intervention_type': intervention_type,
            'stress_indicators': stress_indicators,
            'behavioral_features': current_features,
            'recommendations': self._generate_recommendations(mental_health_score, stress_indicators)
        }
    
    def _calculate_mental_health_score(self, stress_indicators: Dict, features: Dict) -> float:
        """Calculate overall mental health score based on weighted indicators"""
        
        # Base stress calculation
        base_stress = 0.0
        weights = {
            'excessive_tab_switching': 0.25,
            'short_intense_sessions': 0.2,
            'late_night_activity': 0.15,
            'repetitive_behavior': 0.2,
            'productivity_decline': 0.15,
            'typing_inconsistency': 0.05
        }
        
        for indicator, score in stress_indicators.items():
            weight = weights.get(indicator, 0.1)
            base_stress += score * weight
        
        # Contextual adjustments
        session_duration = features.get('session_duration', 0)
        if session_duration > 300:  # Very long sessions (5+ hours)
            base_stress += 0.1
        
        interaction_rate = features.get('interaction_rate', 0)
        if interaction_rate > 20:  # Very high interaction rate
            base_stress += 0.1
        
        return min(1.0, base_stress)
    
    def _determine_intervention(self, mental_health_score: float, stress_indicators: Dict) -> str:
        """Determine type of intervention needed"""
        
        # Check cooldown period
        if (self.last_intervention_time and 
            datetime.now() - self.last_intervention_time < self.intervention_cooldown):
            return 'none'
        
        # Critical intervention (blocking popup)
        if (mental_health_score > 0.8 or 
            stress_indicators.get('late_night_activity', 0) == 1 and mental_health_score > 0.6):
            self.last_intervention_time = datetime.now()
            return 'critical'
        
        # Gentle nudge
        elif mental_health_score > 0.5:
            self.last_intervention_time = datetime.now()
            return 'gentle'
        
        return 'none'
    
    def _generate_recommendations(self, mental_health_score: float, stress_indicators: Dict) -> List[str]:
        """Generate personalized recommendations based on analysis"""
        recommendations = []
        
        if stress_indicators.get('late_night_activity', 0) > 0:
            recommendations.append("Consider establishing a healthy sleep schedule. Late-night screen time can affect your well-being.")
        
        if stress_indicators.get('excessive_tab_switching', 0) > 0.7:
            recommendations.append("Try focusing on one task at a time. Consider using website blockers or focus apps.")
        
        if stress_indicators.get('productivity_decline', 0) > 0.5:
            recommendations.append("Take a short break. Try the 20-20-20 rule: every 20 minutes, look at something 20 feet away for 20 seconds.")
        
        if stress_indicators.get('repetitive_behavior', 0) > 0.8:
            recommendations.append("You seem to be checking the same sites frequently. Consider taking a mindful break.")
        
        if mental_health_score > 0.7:
            recommendations.extend([
                "Practice deep breathing: 4 counts in, hold for 4, out for 4.",
                "Step away from the screen for 5-10 minutes.",
                "Try a quick mindfulness exercise or meditation."
            ])
        
        return recommendations if recommendations else ["Keep up the good work! Your digital habits look healthy."]

class MentalHealthTool:
    """Tool for the LangChain agent to analyze mental health"""
    
    def __init__(self):  
        self.analyzer = MentalHealthAnalyzer()
    
    def analyze_session(self, session_json: str) -> str:
        """Analyze session data and return mental health assessment"""
        try:
            session_data = json.loads(session_json)
            analysis = self.analyzer.analyze_mental_state(session_data)
            
            # Format response for the LLM
            response = {
                'mental_health_score': round(analysis['mental_health_score'], 2),
                'intervention_needed': analysis['intervention_type'],
                'key_concerns': [k for k, v in analysis['stress_indicators'].items() if v > 0.5],
                'recommendations': analysis['recommendations'][:3]  # Top 3 recommendations
            }
            
            return json.dumps(response, indent=2)
            
        except Exception as e:
            return f"Error analyzing session data: {str(e)}"
    
    def get_tool(self):
        return Tool.from_function(
            func=self.analyze_session,
            name="MentalHealthAnalyzer",
            description="Analyze user session data to assess mental health and recommend interventions. Input should be JSON string of session data."
        )

# Initialize tools
tools = [MentalHealthTool().get_tool()]

# Enhanced system prompt for mental health analysis
system_prompt = """<|start_of_role|>system<|end_of_role|>You are a compassionate AI mental health assistant that analyzes user behavior patterns to provide supportive interventions. Your role is to:

1. Analyze user session data for signs of stress, anxiety, or poor digital wellness
2. Provide empathetic, evidence-based recommendations
3. Determine appropriate intervention levels (none, gentle nudge, or critical intervention)
4. Always prioritize user well-being and avoid being judgmental

You have access to the following tools:
{tools}

Based on research in digital wellness and mental health:
- Excessive tab switching (>50 per hour) indicates anxiety or difficulty focusing
- Late-night Browse (after 11 PM) suggests sleep disruption
- Repetitive site checking (>70% of visits to same sites) shows compulsive behavior
- Decreased productivity coupled with increased activity indicates stress
- Very short intense sessions suggest restlessness or agitation

Intervention Guidelines:
- GENTLE: Mental health score 0.5-0.7 → Friendly check-in, breathing exercises
- CRITICAL: Mental health score >0.8 → Blocking intervention with mandatory wellness activity

Use a json blob to specify a tool by providing an action key (tool name) and an action_input key (tool input).
Valid "action" values: "Final Answer" or {tool_names}

When someone provides session data:
1. Use MentalHealthAnalyzer to analyze it
2. Return the result directly as your final answer

Follow this format:
Question: input question to answer
Thought: consider previous and subsequent steps
Action:{{{{
"action": $TOOL_NAME,
"action_input": $INPUT
}}}}

Observation: action result
Thought: I know what to respond
Action:
{{{{
"action": "Final Answer",
"action_input": "Final response to human"
}}}}
Begin! Reminder to ALWAYS respond with a valid json blob of a single action.
<|end_of_text|>"""

human_prompt = """<|start_of_role|>user<|end_of_role|>{input}<|end_of_text|>
{agent_scratchpad}
(reminder to always respond in a JSON blob)"""

assistant_prompt = """<|start_of_role|>assistant<|end_of_role|>"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder("chat_history", optional=True),
    ("human", human_prompt),
    ("assistant", assistant_prompt),
])

prompt = prompt.partial(
    tools=render_text_description_and_args(list(tools)),
    tool_names=", ".join([t.name for t in tools]),
)

message_history = ChatMessageHistory()

chain = (
    RunnablePassthrough.assign(
        agent_scratchpad=lambda x: format_log_to_str(x["intermediate_steps"]),
    )
    | prompt
    | llm
    | JSONAgentOutputParser()
)

agent_executor = AgentExecutor(
    agent=chain,
    tools=tools,
    handle_parsing_errors=True,
    verbose=True,
    max_iterations=3
)

agent_with_chat_history = RunnableWithMessageHistory(
    agent_executor,
    get_session_history=lambda session_id: message_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

def analyze_user_mental_health(session_data_json: str) -> Dict:
    """Main function to analyze user mental health and trigger interventions"""
    try:
        # Direct analysis without the agent chain to avoid prompt issues
        analyzer = MentalHealthAnalyzer()
        session_data = json.loads(session_data_json)
        analysis_result = analyzer.analyze_mental_state(session_data)
        
        # Format the result for compatibility
        formatted_result = {
            'mental_health_score': analysis_result['mental_health_score'],
            'intervention_needed': analysis_result['intervention_type'],
            'key_concerns': [k for k, v in analysis_result['stress_indicators'].items() if v > 0.5],
            'recommendations': analysis_result['recommendations'][:3]
        }
        
        return {
            'status': 'success',
            'analysis': formatted_result,
            'intervention_required': analysis_result['intervention_type'] != 'none',
            'intervention_type': analysis_result['intervention_type'],
            'message': generate_intervention_message(formatted_result),
            'wellness_task': generate_wellness_task(formatted_result) if analysis_result['intervention_type'] == 'critical' else None
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'intervention_required': False
        }

def generate_intervention_message(analysis: Dict) -> str:
    """Generate appropriate intervention message based on analysis"""
    intervention_type = analysis.get('intervention_needed', 'none')
    mental_health_score = analysis.get('mental_health_score', 0)
    
    if intervention_type == 'critical':
        return f"""
        🌟 Hey there! I've noticed some patterns that suggest you might benefit from a quick wellness break.
        
        Your current digital wellness score is {mental_health_score}/1.0, which indicates it's time for some self-care.
        
        Let's take a moment to reset together. I have a simple wellness activity that will help you feel more centered.
        """
    
    elif intervention_type == 'gentle':
        recommendations = analysis.get('recommendations', [])
        return f"""
        👋 Just checking in! How are you feeling right now?
        
        I've noticed you've been quite active online. Here's a gentle reminder to take care of yourself:
        
        💡 {recommendations[0] if recommendations else 'Consider taking a short break to stretch or breathe deeply.'}
        
        Remember, your well-being matters! ✨
        """
    
    return "Everything looks good! Keep up the healthy digital habits! 😊"

def generate_wellness_task(analysis: Dict) -> Dict:
    """Generate mandatory wellness task for critical interventions"""
    key_concerns = analysis.get('key_concerns', [])
    
    if 'late_night_activity' in key_concerns:
        return {
            'type': 'breathing_exercise',
            'title': 'Bedtime Breathing Exercise',
            'description': 'Complete this 2-minute breathing exercise to help prepare for better sleep.',
            'duration': 120,  # 2 minutes
            'instructions': [
                'Sit comfortably and close your eyes',
                'Breathe in slowly for 4 counts',
                'Hold your breath for 4 counts',
                'Exhale slowly for 6 counts',
                'Repeat this cycle 10 times'
            ],
            'completion_criteria': 'complete_breathing_cycles'
        }
    
    elif 'excessive_tab_switching' in key_concerns:
        return {
            'type': 'mindfulness_exercise',
            'title': 'Focus Reset Exercise',
            'description': 'Take 3 minutes to center yourself and improve focus.',
            'duration': 180,  # 3 minutes
            'instructions': [
                'Close all unnecessary browser tabs',
                'Take 5 deep breaths',
                'Write down your top 3 priorities for today',
                'Choose ONE task to focus on next',
                'Set a timer for 25 minutes of focused work'
            ],
            'completion_criteria': 'set_focus_intention'
        }
    
    else:
        return {
            'type': 'general_wellness',
            'title': 'Quick Wellness Break',
            'description': 'A brief moment to reconnect with yourself.',
            'duration': 180,  # 3 minutes
            'instructions': [
                'Stand up and stretch your arms above your head',
                'Take 10 deep breaths',
                'Look away from your screen at something 20 feet away',
                'Drink a glass of water',
                'Set an intention for the next hour'
            ],
            'completion_criteria': 'complete_wellness_routine'
        }

# Alternative function using the LangChain agent (if you want to use the LLM for more sophisticated analysis)
def analyze_with_llm_agent(session_data_json: str) -> Dict:
    """Alternative function using the LangChain agent for LLM-powered analysis"""
    try:
        result = agent_with_chat_history.invoke(
            {"input": f"Please analyze this user session data for mental health indicators: {session_data_json}"},
            config={"configurable": {"session_id": "mental_health_analysis"}}
        )
        
        # Parse the agent's response
        if isinstance(result.get('output'), str):
            try:
                analysis_result = json.loads(result['output'])
            except:
                # If the output is not JSON, create a basic structure
                analysis_result = {
                    'mental_health_score': 0.3,
                    'intervention_needed': 'none',
                    'key_concerns': [],
                    'recommendations': [result['output']]
                }
        else:
            analysis_result = result.get('output', {})
        
        return {
            'status': 'success',
            'analysis': analysis_result,
            'intervention_required': analysis_result.get('intervention_needed', 'none') != 'none',
            'intervention_type': analysis_result.get('intervention_needed', 'none'),
            'message': generate_intervention_message(analysis_result),
            'wellness_task': generate_wellness_task(analysis_result) if analysis_result.get('intervention_needed') == 'critical' else None
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'intervention_required': False
        }

# Helper function to transform new data format to the one expected by the analyzer
def transform_and_aggregate_data(raw_behavior_data: list) -> dict:
    """
    Transforms raw behavior data (list of domain interactions) from 
    latest_behavior_upload.json into the session format expected by the analyzer.
    It processes the first 6 entries from the behavior list.
    """
    # Use only the first 6 entries as requested
    behavior_slice = raw_behavior_data[:6]

    # Initialize the structure for the final formatted data
    formatted_data = {
        "sessionData": {},
        "visitFrequency": {},
        "behaviorData": {},
        "urlTimeSpent": {},
        "distractionUrls": [],
        "productiveUrls": [],
        "rewardPoints": 0,
        "exportedFrom": "ProductivityGuard_Aggregator"
    }

    total_session_time_ms = 0
    latest_timestamp = "1970-01-01T00:00:00.000Z"

    # Aggregate data from the slice
    for entry in behavior_slice:
        domain = entry.get("domain")
        if not domain:
            continue

        # Aggregate for visitFrequency (counting occurrences of each domain in the slice)
        formatted_data["visitFrequency"][domain] = formatted_data["visitFrequency"].get(domain, 0) + 1
        
        # Structure the behaviorData
        if domain not in formatted_data["behaviorData"]:
            formatted_data["behaviorData"][domain] = []
        
        behavior_entry = entry.copy()
        if 'domain' in behavior_entry:
            del behavior_entry['domain']
        formatted_data["behaviorData"][domain].append(behavior_entry)
        
        # Aggregate for urlTimeSpent (converting ms to seconds)
        duration_ms = entry.get("sessionDuration", 0)
        formatted_data["urlTimeSpent"][domain] = formatted_data["urlTimeSpent"].get(domain, 0) + (duration_ms / 1000)
        
        total_session_time_ms += duration_ms

        if entry.get("lastUpdated") and entry.get("lastUpdated") > latest_timestamp:
            latest_timestamp = entry["lastUpdated"]

    # Populate the main sessionData object
    formatted_data["sessionData"] = {
        "sessionTime": total_session_time_ms / 1000,  # Convert total time to seconds
        "tabSwitchCount": len(behavior_slice),  # Using the number of domain interactions as a proxy
        "timestamp": latest_timestamp
    }
    
    # Add other fields for compatibility
    formatted_data["todayStats"] = {
        "activeTime": total_session_time_ms / 1000,
        "distractionTime": 0,
        "productiveTime": 0
    }
    formatted_data["exportTime"] = latest_timestamp

    return formatted_data


if __name__ == "__main__":
    try:
        # Load data from the specified JSON file
        with open('latest_behavior_upload.json', 'r') as f:
            raw_data = json.load(f)
        
        behavior_list = raw_data.get("behavior", [])
        
        if not behavior_list:
            print("No behavior data found in 'latest_behavior_upload.json'.")
        else:
            # Transform the first 6 domains' data into the required format
            transformed_data = transform_and_aggregate_data(behavior_list)
            
            # Convert the Python dictionary to a JSON string to pass to the analysis function
            session_data_json = json.dumps(transformed_data)
            
            print("Analyzing user session from 'latest_behavior_upload.json'...")
            result = analyze_user_mental_health(session_data_json)

            # Print the final analysis result
            print(json.dumps(result, indent=2))
            
            # Check and report the intervention status
            if 'intervention_required' in result:
                print(f"\nIntervention required: {result['intervention_required']}")
                if not result['intervention_required']:
                    print("No intervention needed. User's digital habits appear healthy.")
            else:
                 print("\nAnalysis result does not contain 'intervention_required' key.")

    except FileNotFoundError:
        print("Error: 'latest_behavior_upload.json' not found. Please ensure the file is in the same directory as brain.py.")
    except json.JSONDecodeError:
        print("Error: Could not decode JSON from 'latest_behavior_upload.json'. Please check the file's format.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")