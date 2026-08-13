"""
Database Loader for SQLite with Postgres-compatible DDL.
Loads normalized 3NF entities into SQLite database.
"""
import sqlalchemy as sa
from sqlalchemy import create_engine, text
import polars as pl
import pandas as pd
import logging
import os
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def get_database_url() -> str:
    """Get database URL from .env or default to SQLite."""
    from pathlib import Path
    
    db_url = os.getenv("DATABASE_URL", "sqlite:///robot_vacuum.db")
    
    # Always use absolute path for SQLite
    if db_url.startswith("sqlite:///"):
        # Extract the database file path
        db_file = db_url.replace("sqlite:///", "")
        
        # If it's already an absolute path, use it
        if os.path.isabs(db_file):
            db_path = Path(db_file)
        else:
            # Compute absolute path relative to src directory
            # db_loader.py is in src/etl/, so go up one level to src/
            src_dir = Path(__file__).parent.parent
            db_path = src_dir / db_file
        
        # Ensure absolute path
        db_path = db_path.resolve()
        db_url = f"sqlite:///{db_path}"
    
    logger.info(f"Using database URL: {db_url}")
    logger.info(f"Database absolute path: {db_path if 'db_path' in locals() else 'N/A'}")
    return db_url


def create_postgres_compatible_ddl(engine: sa.Engine) -> None:
    """
    Create tables with Postgres-compatible DDL.
    Uses standard SQL types (VARCHAR, INTEGER, DECIMAL, DATE, TIMESTAMP).
    """
    logger.info("Creating tables with Postgres-compatible DDL...")
    
    ddl_statements = [
        # Manufacturer table
        """
        CREATE TABLE IF NOT EXISTS manufacturer (
            manufacturer_id VARCHAR(50) PRIMARY KEY,
            manufacturer_name VARCHAR(255) NOT NULL
        )
        """,
        
        # Customer table
        """
        CREATE TABLE IF NOT EXISTS customer (
            customer_id VARCHAR(50) PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            customer_email VARCHAR(255),
            customer_zip_code VARCHAR(20),
            customer_address TEXT,
            billing_zip_code VARCHAR(20),
            billing_address TEXT
        )
        """,
        
        # Product table
        """
        CREATE TABLE IF NOT EXISTS product (
            product_id VARCHAR(50) PRIMARY KEY,
            product_name VARCHAR(255) NOT NULL,
            product_description TEXT,
            model_number VARCHAR(100),
            manufacturer_id VARCHAR(50),
            product_price DECIMAL(10, 2),
            unit_price DECIMAL(10, 2),
            lead_time_days INTEGER,
            reliability_score INTEGER,
            fleet_size INTEGER,
            FOREIGN KEY (manufacturer_id) REFERENCES manufacturer(manufacturer_id)
        )
        """,
        
        # Warehouse table
        """
        CREATE TABLE IF NOT EXISTS warehouse (
            warehouse_id VARCHAR(50) PRIMARY KEY,
            warehouse_street_address TEXT,
            warehouse_zip_code VARCHAR(20),
            warehouse_capacity INTEGER
        )
        """,
        
        # DistributionCenter table
        """
        CREATE TABLE IF NOT EXISTS distribution_center (
            distribution_center_id VARCHAR(50) PRIMARY KEY,
            distribution_center_street_address TEXT,
            distribution_center_zip_code VARCHAR(20)
        )
        """,
        
        # Order table (with derived fields)
        """
        CREATE TABLE IF NOT EXISTS "order" (
            order_id VARCHAR(50) PRIMARY KEY,
            order_date TIMESTAMP,
            customer_id VARCHAR(50),
            product_id VARCHAR(50),
            warehouse_id VARCHAR(50),
            distribution_center_id VARCHAR(50),
            quantity INTEGER,
            shipping_cost DECIMAL(10, 2),
            shipping_carrier VARCHAR(50),
            region VARCHAR(50),
            segment VARCHAR(50),
            tax_amount DECIMAL(10, 2),
            discount_amount DECIMAL(10, 2),
            total_amount DECIMAL(10, 2) NOT NULL,
            delivery_status VARCHAR(50) NOT NULL,
            delivery_address TEXT,
            delivery_zip_code VARCHAR(20),
            expected_delivery_date TIMESTAMP,
            actual_delivery_date TIMESTAMP,
            payment_method VARCHAR(50),
            card_number VARCHAR(50),
            card_brand VARCHAR(50),
            promo_code VARCHAR(50),
            FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
            FOREIGN KEY (product_id) REFERENCES product(product_id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouse(warehouse_id),
            FOREIGN KEY (distribution_center_id) REFERENCES distribution_center(distribution_center_id)
        )
        """,
        
        # Review table
        """
        CREATE TABLE IF NOT EXISTS review (
            review_id VARCHAR(50) PRIMARY KEY,
            order_id VARCHAR(50),
            review_rating INTEGER,
            review_text TEXT,
            review_date TIMESTAMP,
            review_sentiment VARCHAR(50),
            FOREIGN KEY (order_id) REFERENCES "order"(order_id)
        )
        """,
        
        # WarehouseProductStock bridge table
        """
        CREATE TABLE IF NOT EXISTS warehouse_product_stock (
            warehouse_id VARCHAR(50),
            product_id VARCHAR(50),
            stock_level INTEGER,
            restock_threshold INTEGER,
            last_restock_date TIMESTAMP,
            last_updated TIMESTAMP,
            PRIMARY KEY (warehouse_id, product_id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouse(warehouse_id),
            FOREIGN KEY (product_id) REFERENCES product(product_id)
        )
        """,
        
        # WarehouseDistributionCenter bridge table
        """
        CREATE TABLE IF NOT EXISTS warehouse_distribution_center (
            warehouse_id VARCHAR(50),
            distribution_center_id VARCHAR(50),
            PRIMARY KEY (warehouse_id, distribution_center_id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouse(warehouse_id),
            FOREIGN KEY (distribution_center_id) REFERENCES distribution_center(distribution_center_id)
        )
        """
    ]
    
    with engine.connect() as conn:
        # SQLite doesn't support DROP CASCADE, so we'll use IF NOT EXISTS
        for ddl in ddl_statements:
            conn.execute(text(ddl))
            conn.commit()
    
    logger.info("Tables created successfully with Postgres-compatible DDL")


def load_entities_to_db(engine: sa.Engine, entities: Dict[str, pl.DataFrame]) -> None:
    """
    Load normalized entities into the database.
    
    Args:
        engine: SQLAlchemy engine
        entities: Dictionary of normalized DataFrames
    """
    logger.info("Loading entities into database...")
    
    # Define load order to respect foreign key constraints
    load_order = [
        'manufacturer',
        'customer',
        'product',
        'warehouse',
        'distribution_center',
        'order',
        'review',
        'warehouse_product_stock',
        'warehouse_distribution_center'
    ]
    
    table_mapping = {
        'manufacturer': 'manufacturer',
        'customer': 'customer',
        'product': 'product',
        'warehouse': 'warehouse',
        'distribution_center': 'distribution_center',
        'order': 'order',
        'review': 'review',
        'warehouse_product_stock': 'warehouse_product_stock',
        'warehouse_distribution_center': 'warehouse_distribution_center'
    }
    
    row_counts = {}
    
    for entity_name in load_order:
        if entity_name not in entities:
            logger.warning(f"Entity {entity_name} not found in entities dictionary")
            continue
        
        df = entities[entity_name]
        table_name = table_mapping[entity_name]
        
        logger.info(f"Loading {entity_name} into {table_name}...")
        
        # Convert Polars DataFrame to Pandas for SQLAlchemy compatibility
        pandas_df = df.to_pandas()
        
        # Handle datetime columns - ensure they're properly formatted
        for col in pandas_df.columns:
            if pandas_df[col].dtype == 'object':
                # Try to detect datetime columns
                try:
                    pandas_df[col] = pd.to_datetime(pandas_df[col], errors='ignore')
                except:
                    pass
        
        # Load data into database
        try:
            # Use if_exists='replace' for first run, 'append' for subsequent runs
            pandas_df.to_sql(
                table_name,
                engine,
                if_exists='replace',
                index=False,
                method='multi',
                chunksize=1000
            )
            row_count = len(pandas_df)
            row_counts[table_name] = row_count
            logger.info(f"✓ Loaded {row_count} rows into {table_name}")
        except Exception as e:
            logger.error(f"✗ Failed to load {table_name}: {str(e)}")
            raise
    
    logger.info("\n=== Loading Summary ===")
    for table_name, count in row_counts.items():
        logger.info(f"{table_name}: {count} rows")
    logger.info("=" * 50)


def run_etl_pipeline() -> None:
    """
    Run the complete ETL pipeline: Load CSV, Transform, Load DB.
    """
    logger.info("=" * 50)
    logger.info("Starting ETL Pipeline")
    logger.info("=" * 50)
    
    # Step 1: Load CSV
    from etl.loader import load_csv
    csv_path = Path(__file__).parent.parent / "data" / "RobotVacuumDepot_MasterData.csv"
    df = load_csv(str(csv_path))
    
    # Step 2: Transform to 3NF
    from etl.transformer import normalize_to_3nf, validate_transformation
    entities = normalize_to_3nf(df)
    validate_transformation(entities)
    
    # Step 3: Load to Database
    db_url = get_database_url()
    engine = create_engine(db_url, echo=False)
    
    create_postgres_compatible_ddl(engine)
    load_entities_to_db(engine, entities)
    
    logger.info("=" * 50)
    logger.info("ETL Pipeline Completed Successfully!")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_etl_pipeline()

