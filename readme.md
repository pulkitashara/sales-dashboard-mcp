# Sales Agent with Model Context Protocol (MCP)

This project demonstrates a powerful sales data analysis agent built in Python. It uses a custom **Model Context Protocol (MCP)** to create a client-server architecture where a natural language processing agent can securely and efficiently query a PostgreSQL database by calling a predefined set of tools.

## 🚀 Demo

Here's a quick look at the agent in action, answering a series of questions about sales data by communicating with the tool server over MCP.

[[Project Demo]](https://drive.google.com/file/d/1bRKXMhCZliytj965b4vfKiAKNpGHJPEN/view?usp=sharing)

## ✨ Features

* **Custom Protocol:** Utilizes the Model Context Protocol (MCP) for robust communication between the client agent and the tool server.
* **Tool-Based Architecture:** Exposes database queries as distinct, easy-to-use "tools" (`GetTopSellingProducts`, `GetCustomerOrders`, etc.).
* **Database Seeder:** Includes a script to populate the PostgreSQL database with thousands of realistic but fake data points for testing.
* **Natural Language Queries:** A simple, rule-based agent (`sales_agent.py`) interprets user questions to select and execute the appropriate tool.
* **Asynchronous Operations:** Built with `asyncio` for efficient, non-blocking I/O operations between the client and server.

## ⚙️ Architecture: How It Works

The project is divided into a client and a server, which communicate using your **Model Context Protocol (MCP)**. This decouples the agent's logic from the database, making the system modular and secure.

The data flows in this order:

**`Agent` ➡️ `MCP` ➡️ `Tool Server` ➡️ `Database`**

1.  **`seeder_data.py` (Data Seeder)**
    * This is the first step. It connects to a PostgreSQL database and uses the **Faker** library to generate and insert mock data for shops, customers, products, and orders. This creates a realistic environment for the agent to query.

2.  **`server.py` (The Tool Server)**
    * This script is the backend powerhouse. It connects to the database and defines several functions (`GetTopSellingProducts`, `GetCustomerOrders`, `GetShopPerformance`).
    * It uses the `@mcp.tool()` decorator to expose these Python functions as "tools" that can be called remotely.
    * It starts an **MCP server** that listens for incoming tool-call requests from any authorized MCP client.

3.  **`sales_agent.py` (The Client Agent)**
    * This is the client application that simulates user interaction.
    * It starts the `server.py` process in the background and establishes a connection to it using an MCP client.
    * The `manual_tool_selection()` function uses simple keyword matching to parse a natural language query (e.g., "Show top 5 products in shop 3") and determines which tool to call and what parameters to send.
    * It sends the structured request to the server via MCP, awaits the result, and prints a formatted, human-readable response.

## ▶️ Usage

To run the project, you need to start the tool server first and then run the client agent in a separate terminal.

**1. Start the Tool Server**

In your terminal, run the following command to start the MCP server:

```bash
uv run mcp dev server.py
```

The server will start and wait for the agent to connect.

**2. Run the Sales Agent**

In a new terminal window, execute the `sales_agent.py` script:

```bash
python sales_agent.py
```

The agent will connect to the running server, execute its queries, and print the results to your terminal.

### Example Output:

```
Query: What are the top 3 products in shop 1?
Using tool: GetTopSellingProducts with params: {'shop_id': 1, 'limit': 3}
Calling GetTopSellingProducts with params: {'shop_id': 1, 'limit': 3}

=== Results ===
1. Product A (Category: Electronics) - Sold: 42
2. Product B (Category: Clothing) - Sold: 35
3. Product C (Category: Groceries) - Sold: 28

Query: Show me orders for customer 5
...
