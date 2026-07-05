WITH prepared_sales AS (
    SELECT
        COALESCE(buyer_group.BuyerMDM, sales.BuyerMDM) AS BuyerMDM,
        sales.Season,
        sales.FinYear,
        CASE
            WHEN CAST(SUBSTRING(sales.FinYear, 1, 4) AS INT64) = sales.Season
            THEN sales.Season
            ELSE 0
        END AS FYear,
        sales.Category,
        sales.TotalWeight,
        sales.Value,
        IF(sales.SaleNo BETWEEN 1 AND 13, 53 + sales.SaleNo, sales.SaleNo) AS SaleAlias
    FROM `data-warehousing-prod.EasyReports.SaleTransactionView` AS sales
    LEFT JOIN `data-warehousing-prod.EasyReports.Parcon-BuyerGroup` AS buyer_group
        ON sales.BuyerMDM = buyer_group.BuyerMDM
),
season_summary AS (
    SELECT
        FYear,
        BuyerMDM,
        SUM(TotalWeight) AS Sold_Qty,
        SUM(Value) AS Total_Value,
        SAFE_DIVIDE(SUM(Value), SUM(TotalWeight)) AS Avg_Price
    FROM prepared_sales
    WHERE FYear IN (2025, 2026)
        AND SaleAlias BETWEEN 14 AND 26
        AND Category = 'CTC'
        AND BuyerMDM = 'TATA CONSUMER PRODUCTS LTD.'
    GROUP BY FYear, BuyerMDM
)
SELECT
    FYear,
    BuyerMDM,
    Sold_Qty,
    Total_Value,
    Avg_Price
FROM season_summary
ORDER BY FYear, BuyerMDM
