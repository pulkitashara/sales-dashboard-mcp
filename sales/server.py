from mcp.server.fastmcp import FastMCP
import psycopg2
from typing import List, Dict, Optional
import logging
from datetime import date

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("sales-assistant")

class DatabaseManager:
    def __init__(self):
        self.conn_params = {
            "dbname": "sales_dashboard",
            "user": "postgres",
            "password": "1234",
            "host": "localhost",
            "port": "5432"
        }
    
    def get_connection(self):
        """Get a database connection"""
        try:
            conn = psycopg2.connect(**self.conn_params)
            logger.info("Successfully connected to PostgreSQL")
            return conn
        except psycopg2.OperationalError as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

# Initialize database manager
db_manager = DatabaseManager()

# Tool: Get top-selling products
@mcp.tool()
def GetTopSellingProducts(shop_id: int, limit: int = 5) -> List[Dict]:
    """Returns the top N selling products for a given shop.
    Args:
        shop_id: The ID of the shop to query
        limit: Number of top products to return (default: 5)
    Returns:
        List of dictionaries with product names, categories, and quantities sold
    """
    try:
        conn = db_manager.get_connection()
        cur = conn.cursor()
        
        query = """
            SELECT p.id, p.name, p.category, SUM(o.quantity) AS total_sold
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.shop_id = %s
            GROUP BY p.id, p.name, p.category
            ORDER BY total_sold DESC
            LIMIT %s;
        """
        cur.execute(query, (shop_id, limit))
        rows = cur.fetchall()
        
        return [{
            "product_id": pid,
            "product": name,
            "category": category,
            "quantity_sold": int(total),
            "shop_id": shop_id
        } for pid, name, category, total in rows]
        
    except Exception as e:
        logger.error(f"Error in GetTopSellingProducts: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

# Tool: Get customer orders
@mcp.tool()
def GetCustomerOrders(
    customer_id: int, 
    start_date: Optional[str] = None, 
    end_date: Optional[str] = None
) -> List[Dict]:
    # --- START OF THE FIX ---
    """Returns order history for a specific customer, with an optional date range.
    Args:
        customer_id: ID of the customer whose orders to retrieve.
        start_date: Optional start date to filter orders (YYYY-MM-DD).
        end_date: Optional end date to filter orders (YYYY-MM-DD).
    Returns:
        A list of dictionaries, each representing an order.
    """
    # --- END OF THE FIX ---
    try:
        conn = db_manager.get_connection()
        cur = conn.cursor()
        
        query = """
            SELECT o.id, p.name, p.category, o.quantity, o.order_date, s.name as shop_name
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN shops s ON o.shop_id = s.id
            WHERE o.customer_id = %s
        """
        params = [customer_id]
        
        if start_date:
            query += " AND o.order_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND o.order_date <= %s"
            params.append(end_date)
            
        query += " ORDER BY o.order_date DESC"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        return [{
            "order_id": oid,
            "product": name,
            "category": category,
            "quantity": quantity,
            "date": str(date),
            "shop": shop_name
        } for oid, name, category, quantity, date, shop_name in rows]
        
    except Exception as e:
        logger.error(f"Error in GetCustomerOrders: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

# Tool: Get shop performance
@mcp.tool()
def GetShopPerformance(shop_id: int) -> Dict:
    """Returns performance metrics for a specific shop.
    Args:
        shop_id: ID of the shop to analyze
    Returns:
        Dictionary with various performance metrics
    """
    try:
        conn = db_manager.get_connection()
        cur = conn.cursor()
        
        # Get basic shop info
        cur.execute("SELECT name, location FROM shops WHERE id = %s", (shop_id,))
        shop_info = cur.fetchone()
        
        # Get total sales
        cur.execute("""
            SELECT COUNT(DISTINCT customer_id) as customers,
                   SUM(quantity) as items_sold,
                   SUM(quantity * p.price) as revenue
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.shop_id = %s
        """, (shop_id,))
        sales_info = cur.fetchone()
        
        # Get top category
        cur.execute("""
            SELECT p.category, SUM(o.quantity) as total
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.shop_id = %s
            GROUP BY p.category
            ORDER BY total DESC
            LIMIT 1
        """, (shop_id,))
        top_category = cur.fetchone()
        
        return {
            "shop_id": shop_id,
            "shop_name": shop_info[0],
            "location": shop_info[1],
            "unique_customers": sales_info[0],
            "total_items_sold": sales_info[1],
            "total_revenue": float(sales_info[2]) if sales_info[2] else 0.0,
            "top_category": top_category[0] if top_category else "N/A",
            "top_category_sales": top_category[1] if top_category else 0
        }
        
    except Exception as e:
        logger.error(f"Error in GetShopPerformance: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    mcp.run(transport="stdio")