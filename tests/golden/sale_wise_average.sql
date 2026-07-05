WITH prepared_sales AS (
    SELECT
        SaleNo,
        Season,
        FinYear,
        CASE
            WHEN CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season
            THEN Season
            ELSE 0
        END AS FYear,
        Category,
        TotalWeight,
        Value,
        IF(SaleNo BETWEEN 1 AND 13, 53 + SaleNo, SaleNo) AS SaleAlias,
        CASE
            WHEN Area = 'AS' THEN 'AS'
            WHEN Area IN ('DO', 'TR') THEN 'DO/TR'
            WHEN Area IN ('CA', 'TP') THEN 'CA/TP'
            ELSE 'OTHERS'
        END AS AreaAlias
    FROM `data-warehousing-prod.EasyReports.SaleTransactionView`
),
sale_summary AS (
    SELECT
        SaleAlias,
        SUM(TotalWeight) AS Sold_Qty,
        SUM(Value) AS Total_Value,
        SAFE_DIVIDE(SUM(Value), SUM(TotalWeight)) AS Avg_Price
    FROM prepared_sales
    WHERE FYear = 2026
        AND SaleAlias = 20
        AND AreaAlias = 'AS'
        AND Category = 'ORTHODOX'
    GROUP BY SaleAlias
)
SELECT
    SaleAlias,
    Sold_Qty,
    Total_Value,
    Avg_Price
FROM sale_summary
ORDER BY SaleAlias
