WITH prepared_sales AS (
    SELECT
        GardenMDM,
        Season,
        FinYear,
        CASE
            WHEN CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season
            THEN Season
            ELSE 0
        END AS FYear,
        Category,
        EstBlf,
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
garden_summary AS (
    SELECT
        GardenMDM,
        SUM(TotalWeight) AS Sold_Qty,
        SUM(Value) AS Total_Value,
        SAFE_DIVIDE(SUM(Value), SUM(TotalWeight)) AS Avg_Price
    FROM prepared_sales
    WHERE FYear = 2026
        AND SaleAlias BETWEEN 14 AND 26
        AND AreaAlias = 'AS'
        AND Category = 'CTC'
        AND EstBlf = 'EST'
    GROUP BY GardenMDM
)
SELECT
    GardenMDM,
    Sold_Qty,
    Total_Value,
    Avg_Price,
    DENSE_RANK() OVER (ORDER BY Avg_Price DESC) AS Rank
FROM garden_summary
ORDER BY Rank, GardenMDM
