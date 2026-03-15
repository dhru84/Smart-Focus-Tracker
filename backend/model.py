import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import numpy as np
from dataclasses import dataclass


@dataclass
class UserContext:
    """User context for personalized interventions"""
    typical_productive_hours: List[int]
    distraction_patterns: Dict[str, float]
    response_history: List[Dict]
    productivity_score: float
    stress_indicators: List[str]


class ProductivityModel:
    """AI model for productivity management and interventions"""
    
    def __init__(self):
        self.intervention_templates = {
            'motivational': [
                "You've been on {domain} for {time_spent} minutes. Is this helping you achieve your goals today?",
                "Take a moment to reflect: Is continuing on {domain} the best use of your time right now?",
                "You're {time_over} minutes over your limit on {domain}. What would make you feel more accomplished?"
            ],
            'reflective': [
                "Before continuing on {domain}, what's one productive task you could complete in the next 10 minutes?",
                "You've exceeded your {domain} limit. What drew you here, and is it still relevant?",
                "Pause and consider: How will you feel about this time on {domain} at the end of the day?"
            ],
            'goal_oriented': [
                "You set limits on {domain} for a reason. What goal were you trying to protect?",
                "Your future self is counting on the choices you make now. Continue on {domain}?",
                "What's one small step toward your goals you could take instead of staying on {domain}?"
            ],
            'time_awareness': [
                "You've spent {time_spent} minutes on {domain} today. How does that align with your priorities?",
                "Time check: {time_spent} minutes on {domain}. Is this how you planned to spend your day?",
                "You're {time_over} minutes over your {domain} limit. How will you use the next 10 minutes?"
            ]
        }
        
        self.user_profiles = {}
        self.behavioral_patterns = {}
        
    def update_distraction_patterns(self, user_id: str, urls: List[Dict]) -> None:
        """Update user's distraction patterns"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                'distraction_urls': [],
                'productive_urls': [],
                'intervention_history': [],
                'performance_metrics': {}
            }
        
        # Ensure urls is a list of dicts with url key
        processed_urls = []
        for url in urls:
            if isinstance(url, str):
                processed_urls.append({'url': url})
            elif isinstance(url, dict) and 'url' in url:
                processed_urls.append(url)
            else:
                print(f"Warning: Invalid URL format: {url}")
        
        self.user_profiles[user_id]['distraction_urls'] = processed_urls
        
    def update_productive_patterns(self, user_id: str, urls: List[Dict]) -> None:
        """Update user's productive patterns"""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                'distraction_urls': [],
                'productive_urls': [],
                'intervention_history': [],
                'performance_metrics': {}
            }
        
        # Ensure urls is a list of dicts with url key
        processed_urls = []
        for url in urls:
            if isinstance(url, str):
                processed_urls.append({'url': url})
            elif isinstance(url, dict) and 'url' in url:
                processed_urls.append(url)
            else:
                print(f"Warning: Invalid URL format: {url}")
        
        self.user_profiles[user_id]['productive_urls'] = processed_urls
        
    def process_usage_data(self, usage_data: Dict) -> None:
        """Process usage data to identify patterns with safer access"""
        try:
            # Use .get() to prevent KeyError if data is incomplete
            user_id = usage_data.get('user_id')
            if not user_id:
                # If there's no user_id, we can't process the data
                return 
            
            domain = usage_data.get('domain', 'unknown')
            duration = usage_data.get('duration', 0)
            interactions = usage_data.get('interactions', {})
            
            # Initialize behavioral patterns if not exists
            if user_id not in self.behavioral_patterns:
                self.behavioral_patterns[user_id] = {
                    'time_patterns': {},
                    'engagement_patterns': {},
                    'productivity_scores': []
                }
            
            # Handle timestamp properly
            timestamp = usage_data.get('timestamp')
            if isinstance(timestamp, str):
                try:
                    # Try parsing ISO format
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    hour = dt.hour
                except:
                    # Fallback to current hour
                    hour = datetime.now().hour
            elif isinstance(timestamp, (int, float)):
                # Assume it's a Unix timestamp in milliseconds
                hour = datetime.fromtimestamp(timestamp / 1000).hour
            else:
                hour = datetime.now().hour
            
            # Update time patterns
            if hour not in self.behavioral_patterns[user_id]['time_patterns']:
                self.behavioral_patterns[user_id]['time_patterns'][hour] = {}
            
            if domain not in self.behavioral_patterns[user_id]['time_patterns'][hour]:
                self.behavioral_patterns[user_id]['time_patterns'][hour][domain] = []
            
            self.behavioral_patterns[user_id]['time_patterns'][hour][domain].append(duration)
            
            # Calculate engagement score based on interactions
            engagement_score = self._calculate_engagement_score(interactions, duration)
            
            if domain not in self.behavioral_patterns[user_id]['engagement_patterns']:
                self.behavioral_patterns[user_id]['engagement_patterns'][domain] = []
            
            self.behavioral_patterns[user_id]['engagement_patterns'][domain].append(engagement_score)
            
            # Update productivity score (simple average for now)
            is_productive = usage_data.get('is_productive', False)
            is_distraction = usage_data.get('is_distraction', False)
            score = duration if is_productive else -duration if is_distraction else 0
            self.behavioral_patterns[user_id]['productivity_scores'].append(score)
            
        except Exception as e:
            print(f"Error processing usage data: {e}")
        
    def _calculate_engagement_score(self, interactions: Dict, duration: int) -> float:
        """Calculate engagement score based on interactions and duration"""
        try:
            # Simple formula: (clicks + scrolls + keystrokes) / duration, normalized
            if not isinstance(interactions, dict):
                return 0.0
                
            total_interactions = sum(interactions.get(key, 0) for key in ['clicks', 'scrolls', 'keystrokes'])
            if duration == 0:
                return 0.0
            return min(1.0, total_interactions / max(1, duration))
        except Exception as e:
            print(f"Error calculating engagement score: {e}")
            return 0.0
    
    def analyze_tab_activity(self, tab_data: Dict) -> Optional[Dict]:
        """Analyze tab activity for patterns and determine if alert is needed"""
        try:
            user_id = tab_data['user_id']
            url = tab_data.get('url', '')
            time_of_day = tab_data.get('time_of_day', datetime.now().hour)
            
            # Simple logic: Check if this is a distraction during non-productive hours
            if user_id in self.user_profiles:
                distractions = self.user_profiles[user_id].get('distraction_urls', [])
                if any(d.get('url', '') == url for d in distractions):
                    # Assume productive hours are 9-17 for demo
                    if not (9 <= time_of_day <= 17):
                        return {'type': 'distraction_alert', 'message': 'This might be a distraction outside productive hours!'}
            return None
        except Exception as e:
            print(f"Error analyzing tab activity: {e}")
            return None
    
    def generate_intervention_question(self, domain: str, excess_time: int, user_context: UserContext) -> str:
        """Generate personalized intervention question"""
        try:
            # Select template type based on user context (e.g., high stress -> reflective)
            if user_context.stress_indicators and any('high' in indicator for indicator in user_context.stress_indicators):
                template_type = 'reflective'
            elif user_context.productivity_score < 0.5:
                template_type = 'motivational'
            else:
                template_type = random.choice(list(self.intervention_templates.keys()))
            
            template = random.choice(self.intervention_templates[template_type])
            time_spent = excess_time + 10  # Assume some base time for demo
            time_over = excess_time
            
            return template.format(domain=domain, time_spent=time_spent, time_over=time_over)
        except Exception as e:
            print(f"Error generating intervention question: {e}")
            return f"You've been on {domain} for a while. Is this the best use of your time right now?"
    
    def process_intervention_response(self, interaction: Dict) -> Dict:
        """Process user's response with safer access"""
        try:
            user_id = interaction.get('user_id')
            if not user_id:
                return {}
            
            answer = str(interaction.get('answer', '')).lower()
            
            # Simple NLP-like processing: Look for positive/negative keywords
            positive_keywords = ['yes', 'productive', 'goal', 'continue', 'help', 'work']
            negative_keywords = ['no', 'distraction', 'stop', 'close', 'waste', 'quit']
            
            reward_points = 0
            updated_limits = None
            
            if any(word in answer for word in positive_keywords):
                reward_points = 10
                updated_limits = {'extended_time': 5}  # Minutes
            elif any(word in answer for word in negative_keywords):
                reward_points = 5
                updated_limits = {'reduced_time': 10}
            
            # Store in history
            if user_id in self.user_profiles:
                self.user_profiles[user_id]['intervention_history'].append(interaction)
            
            result = {}
            if reward_points > 0:
                result['reward_points'] = reward_points
            if updated_limits:
                result['updated_limits'] = updated_limits
            
            return result
        except Exception as e:
            print(f"Error processing intervention response: {e}")
            return {}
    
    def generate_productivity_insights(self, user_data: Dict) -> List[str]:
        """Generate insights from user analytics data"""
        try:
            insights = []
            
            # Example insights based on data
            total_time = user_data.get('total_time', 0)
            if total_time > 480:  # 8 hours in minutes
                insights.append(f"You're spending over {total_time // 60} hours online daily. Consider setting stricter limits.")
            elif total_time > 0:
                insights.append(f"You spent {total_time // 60} hours and {total_time % 60} minutes online today.")
            
            top_distractions = user_data.get('top_distractions', [])
            if top_distractions:
                top = top_distractions[0]
                insights.append(f"Your top distraction is {top}. Try blocking it during work hours.")
            
            # Use behavioral patterns if available
            for user_id in self.behavioral_patterns:
                scores = self.behavioral_patterns[user_id]['productivity_scores']
                if scores:
                    avg_score = np.mean(scores)
                    if avg_score > 0:
                        insights.append(f"Overall productivity is positive with average score {avg_score:.2f}.")
                    else:
                        insights.append(f"Productivity needs improvement; current average score is {avg_score:.2f}.")
                break  # Only use first user's data for now
            
            if not insights:
                insights.append("Keep tracking your usage to get personalized insights!")
            
            return insights
        except Exception as e:
            print(f"Error generating productivity insights: {e}")
            return ["Unable to generate insights at this time. Please try again later."]
    
    def recommend_limit_adjustments(self, performance_data: Dict) -> Dict:
        """Recommend adjustments to time limits based on performance"""
        try:
            recommendations = {
                'distraction_adjustments': {},
                'productive_adjustments': {}
            }
            
            # Simple logic: If overuse on distractions, reduce limits
            distraction_usage = performance_data.get('distraction_usage', {})
            for domain, time in distraction_usage.items():
                if time > 60:  # Over 1 hour
                    recommendations['distraction_adjustments'][domain] = {'new_limit': 30}
            
            productive_usage = performance_data.get('productive_usage', {})
            for domain, time in productive_usage.items():
                if time < 120:  # Under 2 hours
                    recommendations['productive_adjustments'][domain] = {'new_target': 180}
            
            return recommendations
        except Exception as e:
            print(f"Error recommending limit adjustments: {e}")
            return {'distraction_adjustments': {}, 'productive_adjustments': {}}
    
    def generate_daily_summary(self, daily_data: Dict) -> Dict:
        """Generate daily productivity summary"""
        try:
            summary = {
                'total_productive_time': 0,
                'total_distraction_time': 0,
                'key_insights': []
            }
            
            usage_entries = daily_data.get('usage_entries', [])
            for entry in usage_entries:
                duration = entry.get('duration', 0)
                if entry.get('is_productive'):
                    summary['total_productive_time'] += duration
                if entry.get('is_distraction'):
                    summary['total_distraction_time'] += duration
            
            productive_hours = summary['total_productive_time'] / 60
            distraction_hours = summary['total_distraction_time'] / 60
            
            summary['key_insights'].append(f"Productive time: {productive_hours:.1f} hours")
            summary['key_insights'].append(f"Distraction time: {distraction_hours:.1f} hours")
            
            if productive_hours > distraction_hours:
                summary['key_insights'].append("Great job! You were more productive than distracted today.")
            else:
                summary['key_insights'].append("Consider reducing distractions tomorrow for better productivity.")
            
            return summary
        except Exception as e:
            print(f"Error generating daily summary: {e}")
            return {
                'total_productive_time': 0,
                'total_distraction_time': 0,
                'key_insights': ['Unable to generate summary at this time']
            }