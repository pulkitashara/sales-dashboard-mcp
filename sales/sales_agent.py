import asyncio
import json
from typing import List, Dict, Any, Optional
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters

async def query_sales_tool(session: ClientSession, tool_name: str, params: dict) -> Optional[dict]:
    
    try:
        print(f"Calling {tool_name} with params: {params}")
        
        # Call the tool
        response = await session.call_tool(tool_name, params)
        
        # Handle the MCP response format
        if hasattr(response, 'structuredContent') and response.structuredContent:
            return response.structuredContent.get('result')
        elif hasattr(response, 'content') and response.content:
            try:
                # Try to parse TextContent items
                return [json.loads(item.text) for item in response.content 
                       if hasattr(item, 'text') and item.type == 'text']
            except json.JSONDecodeError:
                print("Failed to parse JSON response content")
                return None
        
        print("Unexpected response format:", response)
        return None
        
    except Exception as e:
        print(f"Error calling {tool_name}: {str(e)}")
        return None

def manual_tool_selection(query: str) -> tuple[str, dict]:
    """Manually select tool based on query keywords"""
    query = query.lower()
    
    # Rules for GetTopSellingProducts
    if any(word in query for word in ["top", "best", "selling", "products", "items"]):
        shop_id = 1  # default
        if "shop" in query or "store" in query:
            try:
                shop_id = int(query.split("shop")[1].split()[0].strip())
            except:
                try:
                    shop_id = int(query.split("store")[1].split()[0].strip())
                except:
                    pass
        
        limit = 5  # default
        if "top" in query:
            try:
                limit = int(query.split("top")[1].split()[0].strip())
            except:
                pass
        
        return "GetTopSellingProducts", {"shop_id": shop_id, "limit": limit}
    
    # Rules for GetCustomerOrders
    elif any(word in query for word in ["orders", "purchases", "bought", "customer"]):
        customer_id = 1  # default
        if "customer" in query:
            try:
                customer_id = int(query.split("customer")[1].split()[0].strip())
            except:
                pass
        
        return "GetCustomerOrders", {"customer_id": customer_id}
    
    # Default fallback
    return None, {}

async def process_user_query(query: str, session: ClientSession):
    """Updated query processing with better error handling"""
    tool_name, tool_params = manual_tool_selection(query)
    
    if not tool_name:
        print("I couldn't understand your request. Try these formats:")
        print("- 'Show top 5 products in shop 3'")
        print("- 'List orders for customer 10'")
        return
    
    print(f"Using tool: {tool_name} with params: {tool_params}")
    
    try:
        result = await query_sales_tool(session, tool_name, tool_params)
        
        if not result:
            print("No results found or an error occurred")
            return
        
        print("\n=== Results ===")
        if tool_name == "GetTopSellingProducts":
            if isinstance(result, list):
                for i, item in enumerate(result, 1):
                    if isinstance(item, dict):
                        print(f"{i}. {item.get('product')} (Category: {item.get('category')}) - Sold: {item.get('quantity_sold')}")
                    else:
                        print(f"{i}. {item}")
            else:
                print("Unexpected result format")
                
        elif tool_name == "GetCustomerOrders":
            if isinstance(result, list):
                for order in result:
                    if isinstance(order, dict):
                        print(f"[{order.get('date')}] {order.get('product')} (Qty: {order.get('quantity')}) at {order.get('shop')}")
                    else:
                        print(order)
            else:
                print("Unexpected result format")
                
    except Exception as e:
        print(f"Error processing query: {e}")

async def main():
    server_params = StdioServerParameters(
        command="python",
        args=["server.py"],
        env=None,
    )
    
    try:
        async with (
            stdio_client(server_params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            print("Connected to MCP server")
            
            queries = [
                "What are the top 3 products in shop 1?",
                "Show me orders for customer 5",
                "List the best selling products in shop 2",
                "What did customer 3 purchase?"
            ]
            
            for query in queries:
                print(f"\nQuery: {query}")
                await process_user_query(query, session)
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(main())