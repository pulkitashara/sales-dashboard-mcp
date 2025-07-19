import asyncio
import json
import os
import sys
import traceback
from typing import List, Dict, Any, Optional, Tuple
import logging

import google.generativeai as genai
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Initialize logging
# logging.basicConfig(level=logging.DEBUG)  # Changed to DEBUG for more detailed logs
logger = logging.getLogger(__name__)

# --- LLM Configuration ---
load_dotenv()

# Configure the Gemini API using an environment variable
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    logger.error("GOOGLE_API_KEY not found in .env file or environment variables.")
    logger.error("Please create a .env file and add your key.")
    exit(1)

# --- End LLM Configuration ---

async def query_sales_tool(session: ClientSession, tool_name: str, params: dict) -> Optional[dict]:
    try:
        logger.info(f"Calling {tool_name} with params: {params}")
        
        # First verify the tool exists - handle tuple format
        available_tools = await session.list_tools()
        valid_tools = []
        
        if hasattr(available_tools, 'tools'):
            # If it's a response object with tools attribute
            valid_tools = [tool.name for tool in available_tools.tools]
        elif hasattr(available_tools, '__iter__'):
            # Handle both tuple and list cases
            for tool in available_tools:
                if isinstance(tool, tuple) and len(tool) > 0:
                    valid_tools.append(tool[0])  # First element is tool name
                elif hasattr(tool, 'name'):
                    valid_tools.append(tool.name)
        
        if tool_name not in valid_tools:
            logger.error(f"Invalid tool name: {tool_name}. Valid tools: {valid_tools}")
            return None
            
        # Convert parameters to correct types
        converted_params = {}
        for key, value in params.items():
            if key in ['shop_id', 'customer_id', 'limit']:
                try:
                    converted_params[key] = int(value)
                except (ValueError, TypeError):
                    logger.warning(f"Failed to convert {key} to int, using original value")
                    converted_params[key] = value
            else:
                converted_params[key] = value
        
        # Make the tool call
        response = await session.call_tool(tool_name, converted_params)
        
        # Handle the response - more robust parsing
        if response is None:
            logger.error("Received None response from tool call")
            return None
            
        # Try to get structured content first
        if hasattr(response, 'structuredContent') and response.structuredContent:
            result = response.structuredContent.get('result')
            if result is not None:
                return result
                
        # Try to parse content if available
        if hasattr(response, 'content'):
            content = response.content
            if isinstance(content, str):
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {'raw_content': content}
            elif isinstance(content, (list, dict)):
                return content
            elif hasattr(content, 'text'):
                try:
                    return json.loads(content.text)
                except (json.JSONDecodeError, AttributeError):
                    return {'raw_text': str(content)}
                    
        # If response is already a dict or list, return it directly
        if isinstance(response, (dict, list)):
            return response
            
        # Fallback - try to convert to dict
        try:
            return dict(response)
        except (TypeError, ValueError):
            logger.error(f"Could not convert response to dict: {response}")
            return None
            
    except Exception as e:
        logger.error(f"Error calling {tool_name}: {str(e)}", exc_info=True)
        return None

async def llm_tool_selection(query: str, session: ClientSession) -> Tuple[Optional[str], dict]:
    """
    Uses an LLM to select the appropriate tool and parameters based on the user query.
    """
    logger.info("Asking LLM to select a tool...")
    
    try:
        # Get available tools from the session
        tool_list = await session.list_tools()
        logger.debug(f"Raw tools response: {tool_list}")
        
        # Extract the actual Tool objects from the response
        if hasattr(tool_list, 'tools'):
            available_tools = tool_list.tools
        else:
            available_tools = tool_list
        
        logger.debug(f"Available tools: {available_tools}")
        
        if not available_tools:
            logger.error("No tools available from server")
            return None, {}
            
        # Build the list of valid tools with their descriptions
        valid_tools = []
        for tool in available_tools:
            if hasattr(tool, 'name') and hasattr(tool, 'description'):
                valid_tools.append({
                    "name": tool.name,
                    "description": tool.description
                })
        
        if not valid_tools:
            logger.error("No valid tools found")
            return None, {}
        
        # Build examples based on available tools
        examples = []
        for tool in valid_tools:
            if tool['name'] == "GetTopSellingProducts":
                examples.append({
                    "query": "What are the top 3 products in shop 1?",
                    "response": {
                        "tool_name": "GetTopSellingProducts",
                        "parameters": {"shop_id": 1, "limit": 3}
                    }
                })
            elif tool['name'] == "GetCustomerOrders":
                examples.append({
                    "query": "Show me orders for customer 5 from last month",
                    "response": {
                        "tool_name": "GetCustomerOrders",
                        "parameters": {"customer_id": 5}
                    }
                })
            elif tool['name'] == "GetShopPerformance":
                examples.append({
                    "query": "How is shop 2 performing?",
                    "response": {
                        "tool_name": "GetShopPerformance",
                        "parameters": {"shop_id": 2}
                    }
                })
        
        prompt = f"""
You are a tool selection assistant. Your task is to:
1. Analyze the user query
2. Select exactly one tool from the available tools
3. Extract the correct parameters
4. Return a JSON response with the tool name and parameters

AVAILABLE TOOLS:
{json.dumps(valid_tools, indent=2)}

EXAMPLES:
{json.dumps(examples, indent=2)}

USER QUERY:
"{query}"

Respond STRICTLY with a JSON object containing:
- "tool_name": (must be one of the exact tool names above)
- "parameters": (object with required parameters)

YOUR RESPONSE (ONLY JSON, NO OTHER TEXT):
"""
        logger.debug(f"LLM Prompt:\n{prompt}")
        
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = await model.generate_content_async(prompt)
        
        # Clean and parse the response
        response_text = response.text.strip()
        logger.debug(f"Raw LLM response: {response_text}")
        
        # Extract JSON from response
        try:
            json_str = response_text
            if '```json' in response_text:
                json_str = response_text.split('```json')[1].split('```')[0]
            elif '```' in response_text:
                json_str = response_text.split('```')[1]
                
            parsed_response = json.loads(json_str)
            tool_name = parsed_response.get("tool_name")
            tool_params = parsed_response.get("parameters", {})
            
            # Validate the tool name against our known tools
            valid_tool_names = [tool['name'] for tool in valid_tools]
            if not tool_name or tool_name not in valid_tool_names:
                logger.error(f"Invalid tool name returned: {tool_name}")
                return None, {}
                
            logger.info(f"Selected tool: {tool_name} with params: {tool_params}")
            return tool_name, tool_params
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}\nResponse: {response_text}")
            return None, {}
            
    except Exception as e:
        logger.error(f"Error during tool selection: {e}", exc_info=True)
        return None, {}

async def process_user_query(query: str, session: ClientSession):
    """Processes a user query using LLM-based tool selection."""
    try:
        print(f"\nProcessing query: {query}")
        
        tool_name, tool_params = await llm_tool_selection(query, session)
        
        if not tool_name:
            print("Sorry, I couldn't determine how to process your request.")
            return
        
        print(f"Using tool: {tool_name} with parameters: {tool_params}")
        
        result = await query_sales_tool(session, tool_name, tool_params)
        
        if result is None:
            print("\nError: Could not retrieve the requested information. Possible reasons:")
            print("- The server might not be responding properly")
            print("- The requested data might not exist")
            print("- There might be a connection issue")
            return
        
        print("\n=== Results ===")
        
        try:
            if tool_name == "GetTopSellingProducts":
                if isinstance(result, list):
                    if not result:
                        print("No products found for this shop.")
                        return
                        
                    for i, item in enumerate(result, 1):
                        print(f"{i}. {item.get('product', 'Unknown')} - "
                              f"Category: {item.get('category', 'N/A')}, "
                              f"Sold: {item.get('quantity_sold', 0)}")
                elif isinstance(result, dict):
                    print(f"1. {result.get('product', 'Unknown')} - "
                          f"Category: {result.get('category', 'N/A')}, "
                          f"Sold: {result.get('quantity_sold', 0)}")
                else:
                    print("Unexpected result format. Raw data:")
                    print(json.dumps(result, indent=2))
                    
            # [rest of your display logic...]
            
        except Exception as e:
            logger.error(f"Error displaying results: {e}")
            print("Here's the raw data:")
            print(json.dumps(result, indent=2))
            
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        print("An error occurred while processing your request.")

async def main():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["server.py"],
        env=None,
    )
    
    try:
        async with (
            stdio_client(server_params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            logger.info("Connected to MCP server")

            # Verify tools are available
            available_tools = await session.list_tools()
            logger.info(f"Available tools: {available_tools}")
            
            if not available_tools:
                logger.error("No tools available from the server")
                print("Error: No tools available from server")
                return
            

            queries=[]


            while True:
                queries = [input("Enter your query\n")]
                if queries==["exit"]:
                    break
                for query in queries:
                    await process_user_query(query, session)
                
    except Exception as e:
        logger.error("Unhandled error occurred", exc_info=True)
        print("A system error occurred. Please try again later.")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())