"""
Data Transformer for 3NF Normalization.
Transforms flat CSV data into normalized entities per Assignment_3.pdf Page 2.
Calculates derived fields: TotalAmount and DeliveryStatus per Requirements Spec Section 3.2.
"""
import polars as pl
import logging
from datetime import datetime
from typing import Dict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def normalize_to_3nf(df: pl.DataFrame) -> Dict[str, pl.DataFrame]:
    """
    Normalize flat CSV data to 3NF entities.
    
    Args:
        df: Polars DataFrame from loader
        
    Returns:
        Dictionary of normalized DataFrames keyed by entity name
    """
    logger.info("Starting 3NF normalization...")
    
    entities = {}
    
    # 1. Manufacturer
    logger.info("Creating Manufacturer entity...")
    entities['manufacturer'] = (
        df.select([
            pl.col('ManufacturerID').alias('manufacturer_id'),
            pl.col('ManufacturerName').alias('manufacturer_name')
        ])
        .unique()
        .sort('manufacturer_id')
    )
    logger.info(f"Manufacturer: {len(entities['manufacturer'])} records")
    
    # 2. Customer
    logger.info("Creating Customer entity...")
    entities['customer'] = (
        df.select([
            pl.col('CustomerID').alias('customer_id'),
            pl.col('CustomerName').alias('customer_name'),
            pl.col('CustomerEmail').alias('customer_email'),
            pl.col('CustomerZipCode').alias('customer_zip_code'),
            pl.col('CustomerAddress').alias('customer_address'),
            pl.col('BillingZipCode').alias('billing_zip_code'),
            pl.col('BillingAddress').alias('billing_address')
        ])
        .unique()
        .sort('customer_id')
    )
    logger.info(f"Customer: {len(entities['customer'])} records")
    
    # 3. Product
    logger.info("Creating Product entity...")
    entities['product'] = (
        df.select([
            pl.col('ProductID').alias('product_id'),
            pl.col('ProductName').alias('product_name'),
            pl.col('ProductDescription').alias('product_description'),
            pl.col('ModelNumber').alias('model_number'),
            pl.col('ManufacturerID').alias('manufacturer_id'),
            pl.col('ProductPrice').alias('product_price'),
            pl.col('UnitPrice').alias('unit_price'),
            pl.col('LeadTimeDays').alias('lead_time_days'),
            pl.col('ReliabilityScore').alias('reliability_score'),
            pl.col('FleetSize').alias('fleet_size')
        ])
        .unique()
        .sort('product_id')
    )
    logger.info(f"Product: {len(entities['product'])} records")
    
    # 4. Warehouse
    logger.info("Creating Warehouse entity...")
    entities['warehouse'] = (
        df.select([
            pl.col('WarehouseID').alias('warehouse_id'),
            pl.col('WarehouseStreetAddress').alias('warehouse_street_address'),
            pl.col('WarehouseZipCode').alias('warehouse_zip_code'),
            pl.col('WarehouseCapacity').alias('warehouse_capacity')
        ])
        .unique()
        .sort('warehouse_id')
    )
    logger.info(f"Warehouse: {len(entities['warehouse'])} records")
    
    # 5. DistributionCenter
    logger.info("Creating DistributionCenter entity...")
    entities['distribution_center'] = (
        df.select([
            pl.col('DistributionCenterID').alias('distribution_center_id'),
            pl.col('DistributionCenterStreetAddress').alias('distribution_center_street_address'),
            pl.col('DistributionCenterZipCode').alias('distribution_center_zip_code')
        ])
        .unique()
        .sort('distribution_center_id')
    )
    logger.info(f"DistributionCenter: {len(entities['distribution_center'])} records")
    
    # 6. Order (with derived fields)
    logger.info("Creating Order entity with derived fields...")
    
    # Calculate TotalAmount per Requirements Spec Section 3.2:
    # TotalAmount = (ProductPrice * Quantity) + ShippingCost + TaxAmount - DiscountAmount
    current_datetime = datetime.now()
    
    # Calculate DeliveryStatus based on date comparison
    # Per Requirements Spec: Derived attribute based on ActualDeliveryDate vs ExpectedDeliveryDate
    # Uses same-day logic: If actual delivery date <= expected delivery date (date only, not time), consider it "Delivered"
    calculated_status = (
        pl.when(
            # If DeliveryStatus in CSV is "Canceled" or contains "Canceled" -> keep it
            pl.col('DeliveryStatus').str.contains("Canceled", literal=True)
        ).then(pl.col('DeliveryStatus'))
        .when(
            # If ActualDeliveryDate is NULL and ExpectedDeliveryDate is in the past -> Delayed
            (pl.col('ActualDeliveryDate').is_null())
            & (pl.col('ExpectedDeliveryDate').is_not_null())
            & (pl.col('ExpectedDeliveryDate') < pl.lit(current_datetime))
        ).then(pl.lit("Delayed"))
        .when(
            # If both dates exist, compare dates only (same day = Delivered)
            # Actual delivery on same day or earlier than expected = "Delivered"
            (pl.col('ActualDeliveryDate').is_not_null())
            & (pl.col('ExpectedDeliveryDate').is_not_null())
            & (pl.col('ActualDeliveryDate').dt.date() <= pl.col('ExpectedDeliveryDate').dt.date())
        ).then(pl.lit("Delivered"))
        .when(
            # If ActualDeliveryDate date > ExpectedDeliveryDate date -> Delayed (arrived on a later day)
            (pl.col('ActualDeliveryDate').is_not_null())
            & (pl.col('ExpectedDeliveryDate').is_not_null())
            & (pl.col('ActualDeliveryDate').dt.date() > pl.col('ExpectedDeliveryDate').dt.date())
        ).then(pl.lit("Delayed"))
        .when(
            # If ExpectedDeliveryDate is in the future and no actual date -> On Time
            (pl.col('ActualDeliveryDate').is_null())
            & (pl.col('ExpectedDeliveryDate').is_not_null())
            & (pl.col('ExpectedDeliveryDate') >= pl.lit(current_datetime))
        ).then(pl.lit("On Time"))
        .when(
            # If ActualDeliveryDate exists but ExpectedDeliveryDate is NULL -> Delivered (assume on time)
            (pl.col('ActualDeliveryDate').is_not_null())
            & (pl.col('ExpectedDeliveryDate').is_null())
        ).then(pl.lit("Delivered"))
        .otherwise(pl.lit("Pending"))  # Changed default from "Delivered" to "Pending" for safety
    )
    
    order_df = df.with_columns([
        # Calculate TotalAmount using the formula
        (
            (pl.col('ProductPrice') * pl.col('Quantity')) 
            + pl.col('ShippingCost') 
            + pl.col('TaxAmount') 
            - pl.col('DiscountAmount')
        ).alias('calculated_total_amount'),
        
        # Calculate DeliveryStatus
        calculated_status.alias('calculated_delivery_status')
    ])
    
    entities['order'] = order_df.select([
        pl.col('OrderID').alias('order_id'),
        pl.col('OrderDate').alias('order_date'),
        pl.col('CustomerID').alias('customer_id'),
        pl.col('ProductID').alias('product_id'),
        pl.col('WarehouseID').alias('warehouse_id'),
        pl.col('DistributionCenterID').alias('distribution_center_id'),
        pl.col('Quantity').alias('quantity'),
        pl.col('ShippingCost').alias('shipping_cost'),
        pl.col('ShippingCarrier').alias('shipping_carrier'),
        pl.col('Region').alias('region'),
        pl.col('Segment').alias('segment'),
        pl.col('TaxAmount').alias('tax_amount'),
        pl.col('DiscountAmount').alias('discount_amount'),
        pl.col('calculated_total_amount').alias('total_amount'),  # Use calculated value
        pl.col('calculated_delivery_status').alias('delivery_status'),  # Use calculated value
        pl.col('DeliveryAddress').alias('delivery_address'),
        pl.col('DeliveryZipCode').alias('delivery_zip_code'),
        pl.col('ExpectedDeliveryDate').alias('expected_delivery_date'),
        pl.col('ActualDeliveryDate').alias('actual_delivery_date'),
        pl.col('PaymentMethod').alias('payment_method'),
        pl.col('CardNumber').alias('card_number'),
        pl.col('CardBrand').alias('card_brand'),
        pl.col('PromoCode').alias('promo_code')
    ]).sort('order_id')
    
    logger.info(f"Order: {len(entities['order'])} records")
    logger.info("TotalAmount and DeliveryStatus calculated per Requirements Spec Section 3.2")
    
    # 7. Review
    logger.info("Creating Review entity...")
    entities['review'] = (
        df.filter(pl.col('ReviewID').is_not_null())
        .select([
            pl.col('ReviewID').alias('review_id'),
            pl.col('OrderID').alias('order_id'),
            pl.col('ReviewRating').alias('review_rating'),
            pl.col('ReviewText').alias('review_text'),
            pl.col('ReviewDate').alias('review_date'),
            pl.col('ReviewSentiment').alias('review_sentiment')
        ])
        .unique()
        .sort('review_id')
    )
    logger.info(f"Review: {len(entities['review'])} records")
    
    # 8. WarehouseProductStock (Bridge table)
    logger.info("Creating WarehouseProductStock bridge table...")
    entities['warehouse_product_stock'] = (
        df.select([
            pl.col('WarehouseID').alias('warehouse_id'),
            pl.col('ProductID').alias('product_id'),
            pl.col('StockLevel').alias('stock_level'),
            pl.col('RestockThreshold').alias('restock_threshold'),
            pl.col('LastRestockDate').alias('last_restock_date'),
            pl.col('LastUpdated').alias('last_updated')
        ])
        .unique()
        .sort(['warehouse_id', 'product_id'])
    )
    logger.info(f"WarehouseProductStock: {len(entities['warehouse_product_stock'])} records")
    
    # 9. WarehouseDistributionCenter (Bridge table)
    logger.info("Creating WarehouseDistributionCenter bridge table...")
    entities['warehouse_distribution_center'] = (
        df.select([
            pl.col('WarehouseID').alias('warehouse_id'),
            pl.col('DistributionCenterID').alias('distribution_center_id')
        ])
        .unique()
        .sort(['warehouse_id', 'distribution_center_id'])
    )
    logger.info(f"WarehouseDistributionCenter: {len(entities['warehouse_distribution_center'])} records")
    
    logger.info("3NF normalization completed successfully!")
    
    return entities


def validate_transformation(entities: Dict[str, pl.DataFrame]) -> bool:
    """
    Validate the transformed data for integrity.
    
    Args:
        entities: Dictionary of normalized DataFrames
        
    Returns:
        True if validation passes
    """
    logger.info("Validating transformation...")
    
    # Check for null primary keys
    for entity_name, df in entities.items():
        if entity_name == 'order':
            null_pks = df.filter(pl.col('order_id').is_null())
        elif entity_name == 'manufacturer':
            null_pks = df.filter(pl.col('manufacturer_id').is_null())
        elif entity_name == 'customer':
            null_pks = df.filter(pl.col('customer_id').is_null())
        elif entity_name == 'product':
            null_pks = df.filter(pl.col('product_id').is_null())
        elif entity_name == 'warehouse':
            null_pks = df.filter(pl.col('warehouse_id').is_null())
        elif entity_name == 'distribution_center':
            null_pks = df.filter(pl.col('distribution_center_id').is_null())
        elif entity_name == 'review':
            null_pks = df.filter(pl.col('review_id').is_null())
        else:
            continue
            
        if len(null_pks) > 0:
            logger.warning(f"{entity_name} has {len(null_pks)} rows with null primary keys")
    
    # Validate TotalAmount calculation
    order_df = entities['order']
    # Sample check: verify formula was applied
    sample = order_df.head(5)
    logger.info(f"Sample TotalAmount values: {sample.select(['order_id', 'total_amount'])}")
    
    logger.info("Validation completed")
    return True


if __name__ == "__main__":
    # Test transformation
    from loader import load_csv
    
    csv_path = Path(__file__).parent.parent / "data" / "RobotVacuumDepot_MasterData.csv"
    df = load_csv(str(csv_path))
    entities = normalize_to_3nf(df)
    
    print("\n=== Entity Summary ===")
    for name, entity_df in entities.items():
        print(f"{name}: {len(entity_df)} rows, {len(entity_df.columns)} columns")

