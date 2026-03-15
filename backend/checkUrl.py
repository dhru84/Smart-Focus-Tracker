import os
import requests
import json
import re
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
from urllib.parse import urlparse

from dotenv import load_dotenv # Recommended for MISTRAL_API_KEY
from langchain_mistralai import ChatMistralAI
from bs4 import BeautifulSoup
from langchain.tools import Tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.prompts import PromptTemplate
from langchain.tools.render import render_text_description_and_args
from langchain.agents.output_parsers import JSONAgentOutputParser
from langchain.agents.format_scratchpad import format_log_to_str
from langchain.agents import AgentExecutor
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnablePassthrough

load_dotenv()

# Configuration
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Updated LLM Configuration using Mistral
llm = ChatMistralAI(
    model="mistral-small-latest",
    api_key=MISTRAL_API_KEY,
    temperature=0.3,
    max_tokens=300
)

class URLThoughtsTool:
    def __init__(self):
        self.productive_indicators = [
            'documentation', 'tutorial', 'course', 'learning', 'education', 'research',
            'article', 'blog', 'news', 'professional', 'work', 'project', 'github',
            'stackoverflow', 'wikipedia', 'academic', 'paper', 'study', 'reference',
            'tool', 'productivity', 'business', 'career', 'skill', 'development'
        ]
        
        self.unproductive_indicators = [
            'social media', 'facebook', 'instagram', 'twitter', 'tiktok', 'snapchat',
            'entertainment', 'game', 'gaming', 'meme', 'funny', 'comedy', 'celebrity',
            'gossip', 'shopping', 'buy', 'purchase', 'sale', 'discount', 'deal',
            'streaming', 'video', 'netflix', 'youtube', 'twitch', 'reddit',
            'distraction', 'procrastination', 'leisure', 'fun'
        ]

    def analyze_and_think(self, url):
        try:
            # Parse the URL
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower().replace('www.', '')
            
            # Quick domain-based thoughts
            domain_thoughts = self._think_about_domain(domain)
            
            # Fetch and analyze content
            content_thoughts = self._think_about_content(url)
            
            # Determine if productive
            is_productive = self._is_productive(domain_thoughts, content_thoughts)
            
            if is_productive:
                return "1"
            else:
                # Return concise thoughts for unproductive URLs
                return f"This appears to be unproductive. {self._get_concise_reason(domain_thoughts, content_thoughts)}"
            
        except Exception as e:
            return f"Cannot assess URL: {str(e)}. Recommend caution."

    def _think_about_domain(self, domain):
        if 'github.com' in domain:
            return "This is GitHub - definitely looks like code or development work. Usually productive."
        elif 'stackoverflow.com' in domain:
            return "Stack Overflow - this is where developers solve problems. Very productive for learning."
        elif 'youtube.com' in domain:
            return "YouTube... this could go either way. Might be educational content or just entertainment."
        elif any(social in domain for social in ['facebook', 'instagram', 'twitter', 'tiktok']):
            return "This is social media. Probably going to be a time sink if I'm being honest."
        elif 'wikipedia.org' in domain:
            return "Wikipedia - knowledge rabbit hole incoming, but usually educational."
        elif any(edu in domain for edu in ['.edu', 'coursera', 'udemy', 'khan']):
            return "Educational domain - this looks promising for learning something new."
        elif 'amazon.com' in domain or 'shopping' in domain:
            return "Shopping site - might be productive if it's for work, but could also be impulse buying territory."
        elif 'netflix.com' in domain or 'streaming' in domain:
            return "Streaming service - this is definitely entertainment time, not work time."
        elif 'outlook.com' in domain:
            return "Outlook - Microsoft's email service, definitely work-related and productive."
        else:
            return f"Unfamiliar domain '{domain}' - need to look at the actual content to judge this one."

    def _think_about_content(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Get title
            title = soup.find('title')
            title_text = title.text.strip() if title else 'No title'
            
            # Get some content
            content = soup.get_text()[:500].lower()
            
            # Think about the title and content
            thoughts = f"The title says '{title_text}'. "
            
            # Analyze content for productivity signals
            productive_signals = sum(1 for indicator in self.productive_indicators if indicator in content)
            unproductive_signals = sum(1 for indicator in self.unproductive_indicators if indicator in content)
            
            if productive_signals > unproductive_signals:
                thoughts += "The content seems focused on learning, work, or useful information. "
            elif unproductive_signals > productive_signals:
                thoughts += "The content looks more entertainment-focused or distracting. "
            else:
                thoughts += "The content seems neutral - could be useful or could be a distraction. "
            
            # Add specific observations
            if 'tutorial' in content or 'how to' in content:
                thoughts += "I see tutorial or instructional content - that's usually productive."
            elif 'breaking news' in content or 'latest' in content:
                thoughts += "Looks like news content - informative but could become a time sink."
            elif 'buy now' in content or 'sale' in content:
                thoughts += "I see shopping/sales language - might lead to impulse purchases."
            elif 'funny' in content or 'meme' in content:
                thoughts += "Humor/meme content detected - fun but probably not productive."
            
            return thoughts
            
        except Exception as e:
            return f"Couldn't load the page content to analyze further. The URL structure will have to be enough to go on."

    def _is_productive(self, domain_thoughts, content_thoughts):
        """Determine if URL is productive based on analysis"""
        thoughts_combined = (domain_thoughts + content_thoughts).lower()
        
        positive_words = ['productive', 'learning', 'educational', 'useful', 'work', 'tutorial', 'development', 'github', 'stackoverflow', 'wikipedia', 'outlook', 'email']
        negative_words = ['entertainment', 'distraction', 'time sink', 'shopping', 'social media', 'impulse', 'streaming', 'gaming', 'meme']
        
        positive_count = sum(1 for word in positive_words if word in thoughts_combined)
        negative_count = sum(1 for word in negative_words if word in thoughts_combined)
        
        # More strict criteria for productivity
        return positive_count > negative_count and positive_count >= 2

    def _get_concise_reason(self, domain_thoughts, content_thoughts):
        """Get concise reason why URL is unproductive"""
        thoughts_combined = (domain_thoughts + content_thoughts).lower()
        
        if 'social media' in thoughts_combined:
            return "Social media can be a major time sink."
        elif 'entertainment' in thoughts_combined or 'streaming' in thoughts_combined:
            return "Entertainment content - likely to be distracting."
        elif 'shopping' in thoughts_combined:
            return "Shopping sites can lead to impulse purchases and distraction."
        elif 'gaming' in thoughts_combined or 'meme' in thoughts_combined:
            return "Gaming/meme content is typically unproductive."
        else:
            return "Content appears to be more distracting than productive."

    def get_tool(self):
        return Tool.from_function(
            func=self.analyze_and_think,
            name="URLThoughtsTool",
            description="Analyze a URL and return '1' if productive, or brief thoughts if unproductive."
        )

# Initialize tools
tools = [URLThoughtsTool().get_tool()]

# Modified system prompt for binary output
system_prompt = """<|start_of_role|>system<|end_of_role|>You are an AI that analyzes URLs for productivity. Your job is simple:
- If a URL is productive (educational, work-related, useful for learning), return exactly "1"
- If a URL is unproductive (entertainment, social media, distracting), return the analysis thoughts

You have access to the following tools:<|end_of_text|>
<|start_of_role|>tools<|end_of_role|>
{tools}
<|end_of_text|>
<|start_of_role|>system<|end_of_role|>
Use a json blob to specify a tool by providing an action key (tool name) and an action_input key (tool input).
Valid "action" values: "Final Answer" or {tool_names}

When someone gives you a URL:
1. Use URLThoughtsTool to analyze it
2. Return the result directly as your final answer

Follow this format:
Question: input question to answer
Thought: consider previous and subsequent steps
Action:

{{
  "action": $TOOL_NAME,
  "action_input": $INPUT
}}

Observation: action result
Thought: I know what to respond
Action:

{{
  "action": "Final Answer",
  "action_input": "Final response to human"
}}


Begin! Reminder to ALWAYS respond with a valid json blob of a single action.
<|end_of_text|>"""

human_prompt = """<|start_of_role|>user<|end_of_role|>{input}<|end_of_text|>
{agent_scratchpad}
(reminder to always respond in a JSON blob)"""

assistant_prompt = """<|start_of_role|>assistant<|end_of_role|>"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", human_prompt),
        ("assistant", assistant_prompt),
    ]
)

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
    verbose=False,  # Disabled verbose to hide chain output
    max_iterations=3
)

agent_with_chat_history = RunnableWithMessageHistory(
    agent_executor,
    get_session_history=lambda session_id: message_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)

def extract_thought_and_action_input(captured_output):
    """Extract both Thought and action_input from the captured output"""
    try:
        result = {
            "thought": None,
            "action_input": None
        }
        
        # Look for "Thought" field
        thought_patterns = [
            r'"Thought":\s*"([^"]*)"',
            r"'Thought':\s*'([^']*)'",
        ]
        
        for pattern in thought_patterns:
            matches = re.findall(pattern, captured_output)
            if matches:
                result["thought"] = matches[-1]  # Get the last occurrence
                break
        
        # Look for "action_input" field
        action_input_patterns = [
            r'"action_input":\s*"([^"]*)"',
            r"'action_input':\s*'([^']*)'",
        ]
        
        for pattern in action_input_patterns:
            matches = re.findall(pattern, captured_output)
            if matches:
                result["action_input"] = matches[-1]  # Get the last occurrence
                break
        
        return result
        
    except Exception as e:
        return {"thought": f"Error extracting: {str(e)}", "action_input": None}

def analyze_url(url):
    """Analyze a URL and return both thought and action_input"""
    try:
        # Capture stdout to get the verbose output even when verbose=False
        stdout_buffer = io.StringIO()
        
        # Temporarily enable verbose to capture the parsing errors which contain our data
        original_verbose = agent_executor.verbose
        agent_executor.verbose = True
        
        captured_output = ""
        result = None
        
        try:
            with redirect_stdout(stdout_buffer):
                result = agent_with_chat_history.invoke(
                    {"input": url},
                    config={"configurable": {"session_id": "url_thoughts"}}
                )
        except Exception as invoke_error:
            # Even if invoke fails, we can extract from the captured output
            pass
        finally:
            # Restore original verbose setting
            agent_executor.verbose = original_verbose
        
        # Get the captured output
        captured_output = stdout_buffer.getvalue()
        
        # Extract thought and action_input from the captured output
        extracted = extract_thought_and_action_input(captured_output)
        
        # If we got a successful result, try to extract from that too
        if result and isinstance(result, dict):
            if "output" in result:
                # Sometimes the result might be in the output field
                result_extracted = extract_thought_and_action_input(str(result["output"]))
                if result_extracted["action_input"]:
                    extracted["action_input"] = result_extracted["action_input"]
        
        return extracted
        
    except Exception as e:
        return {"thought": f"Error analyzing URL: {str(e)}", "action_input": None}

def analyze_url_clean(url):
    """Clean version that returns only the final values"""
    result = analyze_url(url)
    
    # Return formatted result
    if result["action_input"] and result["thought"]:
        return {
            "thought": result["thought"],
            "action_input": result["action_input"]
        }
    elif result["action_input"]:
        return {"action_input": result["action_input"]}
    elif result["thought"]:
        return {"thought": result["thought"]}
    else:
        return {"error": "Could not extract thought or action_input"}

# Example usage
if __name__ == "__main__":
    # Test with URLs
    test_urls = [
        "https://www.outlook.com",
        "https://github.com/microsoft/vscode", 
        "https://www.netflix.com",
        "https://stackoverflow.com/questions/12345"
    ]
    
    print("=== Clean URL Analysis (No Chain Output) ===")
    for url in test_urls:
        print(f"URL: {url}")
        result = analyze_url_clean(url)
        
        if "thought" in result:
            print(f"Thought: {result['thought']}")
        if "action_input" in result:
            print(f"Action Input: {result['action_input']}")
        if "error" in result:
            print(f"Error: {result['error']}")
        
        print("-" * 50)