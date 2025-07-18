import psycopg2
from faker import Faker
from random import randint, choice
from tqdm import tqdm
import datetime

fake = Faker()

conn = psycopg2.connect(
    dbname="sales_dashboard",
    user="postgres",        
    password="1234",  
    host="localhost",
    port="5432"
)
cur = conn.cursor()

# Config
NUM_SHOPS = 5
CUSTOMERS_PER_SHOP = 100
PRODUCTS_PER_SHOP = 20
ORDERS_PER_SHOP = 200

# 1. Shops
shop_ids = []
for _ in range(NUM_SHOPS):
    name = fake.company()
    location = fake.city()
    cur.execute("INSERT INTO shops (name, location) VALUES (%s, %s) RETURNING id", (name, location))
    shop_ids.append(cur.fetchone()[0])

conn.commit()

# 2. Customers, Products, Orders
for shop_id in tqdm(shop_ids, desc="Seeding Shops"):

    # Customers
    customer_ids = []
    for _ in range(CUSTOMERS_PER_SHOP):
        name = fake.name()
        email = fake.unique.email()
        region = choice(['North', 'South', 'East', 'West'])
        cur.execute("INSERT INTO customers (shop_id, name, email, region) VALUES (%s, %s, %s, %s) RETURNING id",
                    (shop_id, name, email, region))
        customer_ids.append(cur.fetchone()[0])

    # Products
    product_ids = []
    categories = ['Electronics', 'Clothing', 'Furniture', 'Books', 'Groceries']
    for _ in range(PRODUCTS_PER_SHOP):
        name = fake.word().capitalize() + " " + fake.word().capitalize()
        category = choice(categories)
        price = round(randint(100, 10000) / 100, 2)
        cur.execute("INSERT INTO products (shop_id, name, category, price) VALUES (%s, %s, %s, %s) RETURNING id",
                    (shop_id, name, category, price))
        product_ids.append(cur.fetchone()[0])

    # Orders
    for _ in range(ORDERS_PER_SHOP):
        customer_id = choice(customer_ids)
        product_id = choice(product_ids)
        quantity = randint(1, 5)
        days_ago = randint(1, 365)
        order_date = datetime.date.today() - datetime.timedelta(days=days_ago)
        cur.execute("""
            INSERT INTO orders (shop_id, customer_id, product_id, quantity, order_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (shop_id, customer_id, product_id, quantity, order_date))

    conn.commit()

print("✅ Dataset created successfully.")
