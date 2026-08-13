"""
CSV Loader using Polars for high-performance data ingestion.
Reads and cleans the RobotVacuumDepot_MasterData.csv file.
"""
import polars as pl
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_csv(csv_path: str) -> pl.DataFrame:
    """
    Load CSV file using Polars with data cleaning.
    
    Args:
        csv_path: Path to the CSV file
        
    Returns:
        Polars DataFrame with cleaned data
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    logger.info(f"Loading CSV from: {csv_path}")
    
    # Read CSV with Polars
    # Handle date parsing and type inference
    df = pl.read_csv(
        csv_path,
        try_parse_dates=True,
        infer_schema_length=10000,
        null_values=["", "NULL", "null", "N/A", "n/a"]
    )
    
    logger.info(f"Loaded {len(df)} rows, {len(df.columns)} columns")
    logger.info(f"Columns: {df.columns}")
    
    # Basic cleaning: ensure numeric columns are properly typed
    numeric_columns = [
        'ShippingCost', 'ProductPrice', 'TaxAmount', 'DiscountAmount', 
        'TotalAmount', 'StockLevel', 'WarehouseCapacity', 'LeadTimeDays',
        'ReliabilityScore', 'UnitPrice', 'FleetSize', 'RestockThreshold',
        'Quantity', 'ReviewRating'
    ]
    
    for col in numeric_columns:
        if col in df.columns:
            df = df.with_columns(
                pl.col(col).cast(pl.Float64, strict=False)
            )
    
    # Parse date columns explicitly
    date_columns = [
        'OrderDate', 'ExpectedDeliveryDate', 'ActualDeliveryDate',
        'LastRestockDate', 'LastUpdated', 'ReviewDate'
    ]
    
    for col in date_columns:
        if col in df.columns:
            # Try to parse dates with multiple format attempts
            # First try format with time, then fallback to date only
            parsed_with_time = pl.col(col).str.strptime(pl.Datetime, format="%m/%d/%Y %H:%M", strict=False)
            parsed_date_only = pl.col(col).str.strptime(pl.Datetime, format="%m/%d/%Y", strict=False)
            
            # Use coalesce to try first format, then second if first is null
            df = df.with_columns(
                pl.coalesce([parsed_with_time, parsed_date_only]).alias(col)
            )
    
    logger.info("Data cleaning completed")
    logger.info(f"DataFrame shape: {df.shape}")
    
    return df


if __name__ == "__main__":
    # Test loading
    csv_path = Path(__file__).parent.parent / "data" / "RobotVacuumDepot_MasterData.csv"
    df = load_csv(str(csv_path))
    print(f"\nSample data (first 3 rows):")
    print(df.head(3))

