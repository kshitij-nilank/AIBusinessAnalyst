--------------------------------------------------------------
CREATING WORKING TABLE AUCTION
--------------------------------------------------------------
SELECT

Case when CAST(substring(FinYear,1,4) as INT64) = Season then Season else 0 end as FYear,
if(SaleNo>=1 AND SaleNo<=13,53+SaleNo,SaleNo) AS SaleAlies,
Case when Area IN ("AS") and Centre IN("KOL","GUW") then "AS"
when Area IN ("DO","TR") and Centre IN("KOL","SIL") then "DO/TR" 
when Area IN ("CA","TP") and Centre IN("KOL","GUW") then "CA/TP" else "" end as AreaAlies,
MDMGradeGroup,


coalesce(SUM(IF(LotStatus = 'Sold',TotalWeight,InvoiceWeight))) AS Offer_Qty,
coalesce(SUM(TotalWeight)) AS Sold_Qty,
ROUND( SAFE_DIVIDE(SUM(Value) , SUM(TotalWeight)) ,2) AS Avg_Price,
coalesce(SUM(Value)) AS Total_Value


FROM 

data-warehousing-prod.EasyReports.SaleTransactionView


WHERE 

Season Between 2025 and 2025 and EstBlf IN ("EST","BLF") and Category IN ("ORTHODOX") and Area IN ("AS") and Centre IN ("KOL") AND
if(SaleNo>=1 AND SaleNo<=13,53+SaleNo,SaleNo) between 14 and 60


GROUP BY 
FYear, SaleAlies, AreaAlies, MDMGradeGroup

HAVING 
FYear <> 0

-------------------------------
CREATING WORKING TABLE TMART
-------------------------------
SELECT 
    CASE WHEN FinYear IS NOT NULL AND LENGTH(FinYear) >= 4 
    AND CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season THEN Season ELSE 0 END AS FYear,GPDATE,EstBlf,
    CASE 
    WHEN Area = "AS" AND Centre IN ("KOL", "GUW") THEN "AS"
    WHEN Area IN ("DO", "TR") AND Centre IN ("KOL", "SIL") THEN "DO/TR"
    WHEN Area IN ("CA", "TP") AND Centre IN ("KOL", "GUW") THEN "CA/TP" 
	ELSE "" END AS AreaAlies,
	GardenMDM,
	SellerGroup, 
    SUM(TotalWeight) AS Offer_Qty,
    COALESCE(SUM(IF(Status = 'Sold', TotalWeight, 0)), 0) AS Sold_Qty,
    COALESCE(SUM(TotalValue), 0) AS Total_Value,
    ROUND(SAFE_DIVIDE(SUM(TotalValue), SUM(IF(Status = 'Sold', TotalWeight, 0))), 2) AS AvgPrice
    FROM data-warehousing-prod.EasyReports.TeaMart
    WHERE 
        SEASON = 2024 AND CATEGORY IN ('ORTHODOX') AND EstBlf IN ("EST") AND Centre IN ("KOL", "GUW") AND Area IN ("AS") 
        AND IF(WeekNo >= 1 AND WeekNo <= 13, 52 + WeekNo, WeekNo) BETWEEN 14 AND 52
    GROUP BY Season, FYear, AreaAlies, GardenMDM, SellerGroup,GPDATE,EstBlf
	Having SUM(IF(Status = 'Sold', TotalWeight, 0))>0 and FYear<>0


--------------------------------------------------------------
CREATING WORKING TABLE TEA INNTECH
--------------------------------------------------------------

Select Season as FYear,
"Kol" as Centre,
"ORTHODOX" as Category,
GardenMDM,
SellerGroup,
"TeaInnTech" as BrokerCode,
SUM(Pkgs) as Pkgs,
SUM(OfferQty) AS InvoiceWeight,
"TeaInnTech" as Mode

FROM data-warehousing-prod.EasyReports.TI

Where Season IN (2024,2025) and if(SaleNo >=1 and SaleNo <=13, 52+SaleNo,SaleNo) between 14 and 26

Group By FYear,Centre,Category,GardenMDM,SellerGroup,BrokerCode,Mode

--------------------------------------------------------------
MULTIPLE AREA BATTING ORDER 
--------------------------------------------------------------

SELECT 
Case when CAST(substring(FinYear,1,4) as INT64) = Season then Season else 0 end as FYear,
coalesce(GardenMDM,"") as GardenMDM,
coalesce(Category,"") as Category,
Area, 
EstBlf,
coalesce( ROUND(sum(Value),0),0) as Total_Value,
coalesce(ROUND(sum(TotalWeight),0),0) as Sold_Qty,
CASE 
	WHEN sum(TotalWeight) >=100000  
	then dense_rank() OVER (Partition by concat(FinYear,Season,EstBlf,CASE WHEN Area = "AS" then "AS"
    WHEN Area IN ("DO","TR") then "DO/TR" end) order by if(sum(TotalWeight) >=100000,SUM(Value) / SUM(TotalWeight),0) DESC) else 0 end as BOP

FROM `data-warehousing-prod.EasyReports.SaleTransactionView`

WHERE 
  Area IN("AS","DO","TR") AND Category = "CTC" and EstBlf IN ("EST","BLF") AND Centre IN("KOL","GUW","SIL") AND if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 52 AND Season between 2023 and 2024
  
GROUP BY 
FinYear,Season, FYear, GardenMDM,Category,Area, EstBlf

HAVING 
sum(TotalWeight)>0.0001 and FYear !=0 and Area <>""


select t1.FYear, t1.GardenMDM, t1.AreaAlies, t1.EstBlf, t1.Category, t1.SubTeaType, t1.GradeMDM, t1.Offer_Qty, t1.Sold_Qty, t1.Total_Value, t2.BOP
from t1 left join t2 on t1.FYear = t2.FYear and t1.GardenMDM = t2.GardenMDM and t1.Area = t2.Area and t1.EstBlf = t2.EstBlf

--------------------------------------------------------------
TMART 
--------------------------------------------------------------


with SaleTransactionView AS (
SELECT 
	CASE WHEN FinYear IS NOT NULL AND LENGTH(FinYear) >= 4 
    AND CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season THEN Season ELSE 0 END AS FYear,GPDATE,EstBlf,
CASE WHEN Area = "AS" AND Centre IN ("KOL", "GUW") THEN "AS"
    WHEN Area IN ("DO", "TR") AND Centre IN ("KOL", "SIL") THEN "DO/TR"
    WHEN Area IN ("CA", "TP") AND Centre IN ("KOL", "GUW") THEN "CA/TP" 
    ELSE "" END AS AreaAlies,
    GardenMDM, SellerGroup,
    COALESCE(SUM(IF(LotStatus = 'Sold', TotalWeight, InvoiceWeight)), 0) AS Offer_Qty,
    SUM(TotalWeight) AS Sold_Qty,
    COALESCE(SUM(Value), 0) AS Total_Value,
    ROUND(SAFE_DIVIDE(SUM(Value), SUM(TotalWeight)), 2) AS AvgPrice
    FROM data-warehousing-prod.EasyReports.SaleTransactionView 
    WHERE 
        SEASON IN (2023,2024) AND CATEGORY IN ('ORTHODOX') AND EstBlf IN ("EST") AND Centre IN ("KOL", "GUW") AND Area IN ("AS") 
        AND IF(SaleNo >= 1 AND SaleNo <= 13, 52 + SaleNo, SaleNo) BETWEEN 14 AND 52
    GROUP BY FYear, AreaAlies, GardenMDM, SellerGroup,GPDATE,EstBlf
	Having sum(TotalWeight)>0 and FYear<>0),
	
TeaMart AS (
    SELECT 
    CASE WHEN FinYear IS NOT NULL AND LENGTH(FinYear) >= 4 
    AND CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season THEN Season ELSE 0 END AS FYear,GPDATE,EstBlf,
    CASE 
    WHEN Area = "AS" AND Centre IN ("KOL", "GUW") THEN "AS"
    WHEN Area IN ("DO", "TR") AND Centre IN ("KOL", "SIL") THEN "DO/TR"
    WHEN Area IN ("CA", "TP") AND Centre IN ("KOL", "GUW") THEN "CA/TP" 
	ELSE "" END AS AreaAlies,
	GardenMDM,SellerGroup, 
    SUM(TotalWeight) AS Offer_Qty,
    COALESCE(SUM(IF(Status = 'Sold', TotalWeight, 0)), 0) AS Sold_Qty,
    COALESCE(SUM(TotalValue), 0) AS Total_Value,
    ROUND(SAFE_DIVIDE(SUM(TotalValue), SUM(IF(Status = 'Sold', TotalWeight, 0))), 2) AS AvgPrice
    FROM data-warehousing-prod.EasyReports.TeaMart
    WHERE 
        SEASON = 2024 AND CATEGORY IN ('ORTHODOX') AND EstBlf IN ("EST") AND Centre IN ("KOL", "GUW") AND Area IN ("AS") 
        AND IF(WeekNo >= 1 AND WeekNo <= 13, 52 + WeekNo, WeekNo) BETWEEN 14 AND 52
    GROUP BY Season, FYear, AreaAlies, GardenMDM, SellerGroup,GPDATE,EstBlf
	Having SUM(IF(Status = 'Sold', TotalWeight, 0))>0 and FYear<>0),

main_table as(
	Select *,"Auction" as Mode from SaleTransactionView Union All Select *,"TeaMart" as Mode from TeaMart )


Select FYear,AreaAlies,GardenMDM,EstBlf,SellerGroup,
SUM(Offer_Qty) as Offer_Qty,
SUM(Sold_Qty) as Sold_Qty,
SUM(Total_Value) as Total_Value,
CASE WHEN SUM(Sold_Qty) > 0 THEN SUM(Total_Value) / SUM(Sold_Qty) ELSE 0 END AS Avg_Value,

case when sum(Sold_Qty)>=100000 then dense_rank() OVER 
(Partition by FYear order by if(sum(Sold_Qty)>=100000,SUM(Total_Value) / SUM(Sold_Qty),0) DESC) else 0 end 
AS BOP FROM main_table
group by FYear,AreaAlies,GardenMDM,SellerGroup,EstBlf;





--------------------------------------------------------------
TMART WITH FLUSH
--------------------------------------------------------------


with SaleTransactionView AS (
SELECT 
	CASE WHEN FinYear IS NOT NULL AND LENGTH(FinYear) >= 4 
    AND CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season THEN Season ELSE 0 END AS FYear,GPDATE,
CASE WHEN Area = "AS" AND Centre IN ("KOL", "GUW") THEN "AS"
    WHEN Area IN ("DO", "TR") AND Centre IN ("KOL", "SIL") THEN "DO/TR"
    WHEN Area IN ("CA", "TP") AND Centre IN ("KOL", "GUW") THEN "CA/TP" 
    ELSE "" END AS AreaAlies,
    GardenMDM, SellerGroup,
    COALESCE(SUM(IF(LotStatus = 'Sold', TotalWeight, InvoiceWeight)), 0) AS Offer_Qty,
    SUM(TotalWeight) AS Sold_Qty,
    COALESCE(SUM(Value), 0) AS Total_Value,
    ROUND(SAFE_DIVIDE(SUM(Value), SUM(TotalWeight)), 2) AS AvgPrice
    FROM data-warehousing-prod.EasyReports.SaleTransactionView 
    WHERE 
        SEASON IN (2024) AND CATEGORY IN ('ORTHODOX') AND EstBlf IN ("EST") AND Centre IN ("KOL", "GUW") AND Area IN ("AS") 
        AND IF(SaleNo >= 1 AND SaleNo <= 13, 52 + SaleNo, SaleNo) BETWEEN 14 AND 52
    GROUP BY FYear, AreaAlies, GardenMDM, SellerGroup,GPDATE
	Having sum(TotalWeight)>0 and FYear<>0),
	
TeaMart AS (
    SELECT 
    CASE WHEN FinYear IS NOT NULL AND LENGTH(FinYear) >= 4 
    AND CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season THEN Season ELSE 0 END AS FYear,GPDATE,
    CASE 
    WHEN Area = "AS" AND Centre IN ("KOL", "GUW") THEN "AS"
    WHEN Area IN ("DO", "TR") AND Centre IN ("KOL", "SIL") THEN "DO/TR"
    WHEN Area IN ("CA", "TP") AND Centre IN ("KOL", "GUW") THEN "CA/TP" 
	ELSE "" END AS AreaAlies,
	GardenMDM,SellerGroup, 
    SUM(TotalWeight) AS Offer_Qty,
    COALESCE(SUM(IF(Status = 'Sold', TotalWeight, 0)), 0) AS Sold_Qty,
    COALESCE(SUM(TotalValue), 0) AS Total_Value,
    ROUND(SAFE_DIVIDE(SUM(TotalValue), SUM(IF(Status = 'Sold', TotalWeight, 0))), 2) AS AvgPrice
    FROM data-warehousing-prod.EasyReports.TeaMart
    WHERE 
        SEASON = 2024 AND CATEGORY IN ('ORTHODOX') AND EstBlf IN ("EST") AND Centre IN ("KOL", "GUW") AND Area IN ("AS") 
        AND IF(WeekNo >= 1 AND WeekNo <= 13, 52 + WeekNo, WeekNo) BETWEEN 14 AND 52
    GROUP BY Season, FYear, AreaAlies, GardenMDM, SellerGroup,GPDATE
	Having SUM(IF(Status = 'Sold', TotalWeight, 0))>0 and FYear<>0),

main_table as(
	Select *,"Auction" as Mode from SaleTransactionView Union All Select *,"TeaMart" as Mode from TeaMart ),
t2 as(
Select *, 
case 
		WHEN GPDATE BETWEEN '2024-02-17' AND '2024-05-21' THEN "Flush-I"
        WHEN GPDATE BETWEEN '2024-05-22' AND '2024-07-15' THEN "Flush-II"
        WHEN GPDATE BETWEEN '2024-07-16' AND '2024-08-15' THEN "Rain-I"
        WHEN GPDATE BETWEEN '2024-08-16' AND '2024-10-25' THEN "Rain-II"
        WHEN GPDATE BETWEEN '2024-10-26' AND '2025-03-31' THEN "PostPuja"
		else "" end as RangeAlies
from main_table),

table1 as(
	Select RangeAlies,AreaAlies,GardenMDM,SellerGroup,
	SUM(Offer_Qty) as Offer_Qty,
	SUM(Sold_Qty) as Sold_Qty,
	SUM(Total_Value) as Total_Value,
	CASE WHEN SUM(Sold_Qty) > 0 THEN SUM(Total_Value) / SUM(Sold_Qty) ELSE 0 END AS Avg_Value,
	CASE 
	WHEN SUM(Sold_Qty) >= 50000 AND RangeAlies = "Flush-I" THEN DENSE_RANK() OVER(PARTITION BY RangeAlies ORDER BY if(sum(Sold_Qty)>=50000, SUM(Total_Value) / SUM(Sold_Qty),0) DESC)
    WHEN SUM(Sold_Qty) >= 50000 AND RangeAlies = "Flush-II" THEN DENSE_RANK() OVER (PARTITION BY RangeAlies ORDER BY if(sum(Sold_Qty)>=50000, SUM(Total_Value) / SUM(Sold_Qty),0) DESC)
    WHEN SUM(Sold_Qty) >= 50000 AND RangeAlies = "Rain-I" THEN DENSE_RANK() OVER (PARTITION BY RangeAlies ORDER BY if(sum(Sold_Qty)>=50000,SUM(Total_Value) / SUM(Sold_Qty),0) DESC)
    WHEN SUM(Sold_Qty) >= 50000 AND RangeAlies = "Rain-II" THEN DENSE_RANK() OVER (PARTITION BY RangeAlies ORDER BY if(sum(Sold_Qty)>=50000,SUM(Total_Value) / SUM(Sold_Qty),0) DESC)
    WHEN SUM(Sold_Qty) >= 50000 AND RangeAlies = "PostPuja" THEN DENSE_RANK() OVER (PARTITION BY RangeAlies ORDER BY if(sum(Sold_Qty)>=50000,SUM(Total_Value) / SUM(Sold_Qty),0) DESC)
    ELSE 0
	END AS ESTBOP
	
	from t2 group by RangeAlies,AreaAlies,GardenMDM,SellerGroup),
	
#Select * from table1;

t3 as(Select *,
case when GPDATE between '2024-02-17' and '2025-03-31' then "Dist" else "" end as RangeAlies from main_table),

table2 as
(SELECT RangeAlies,AreaAlies,GardenMDM,SellerGroup, 
	SUM(Offer_Qty) as Offer_Qty,
	SUM(Sold_Qty) as Sold_Qty,
	SUM(Total_Value) as Total_Value,
	CASE WHEN SUM(Sold_Qty) > 0 THEN SUM(Total_Value) / SUM(Sold_Qty) ELSE 0 END AS Avg_Value,
case when sum(Sold_Qty)>=75000 then dense_rank() OVER 
(Partition by RangeAlies order by if(sum(Sold_Qty)>=75000,SUM(Total_Value) / SUM(Sold_Qty),0) DESC) else 0 end 
AS ESTBOP from t3

group by RangeAlies,AreaAlies,GardenMDM,SellerGroup)

Select * from table1
Union All
Select * from table2;





--------------------------------------------------------------
QUARTERWISE BATTING ORDER ON GPDATE
--------------------------------------------------------------

	WITH t1 AS (
		SELECT
		CASE WHEN CAST(SUBSTRING(FinYear, 1, 4) AS INT64) = Season THEN Season ELSE 0 END AS FYear,
		CASE
		WHEN EXTRACT(MONTH FROM PARSE_DATE('%d/%m/%Y', AuctionDate)) IN (4, 5, 6) THEN 'Q1'
		WHEN EXTRACT(MONTH FROM PARSE_DATE('%d/%m/%Y', AuctionDate)) IN (7, 8, 9) THEN 'Q2'
		WHEN EXTRACT(MONTH FROM PARSE_DATE('%d/%m/%Y', AuctionDate)) IN (10, 11, 12) THEN 'Q3'
		WHEN EXTRACT(MONTH FROM PARSE_DATE('%d/%m/%Y', AuctionDate)) IN (1, 2, 3) THEN 'Q4' ELSE ""
	END AS AuctionQuarter,
			GardenMDM,
			COALESCE(SUM(TotalWeight), 0) AS Sold_Qty,
			COALESCE(SUM(Value), 0) AS Total_Value
		FROM 
			`data-warehousing-prod.EasyReports.SaleTransactionView`
		WHERE 
			Area IN ("AS") and Centre IN ("GUW") and Category IN ("CTC") AND EstBlf IN ("EST") AND (IF(SaleNo >= 1 AND SaleNo <= 13, 52 + SaleNo, SaleNo)) BETWEEN 14 AND 55 AND Season BETWEEN 2023 AND 2024
		GROUP BY FinYear, Season, GardenMDM, AuctionDate,AuctionQuarter
		HAVING FYear <> 0),
	t2 AS (
		SELECT 
			FYear,
			AuctionQuarter,
			GardenMDM,
			SUM(Sold_Qty) AS Total_Sold_Qty,
			SUM(Total_Value) AS Total_Value,
			CASE 
				WHEN SUM(Sold_Qty) > 0 THEN SUM(Total_Value) / SUM(Sold_Qty)
				ELSE 0 
			END AS Avg_Value_Per_Unit
		FROM t1
		GROUP BY FYear,AuctionQuarter, GardenMDM),
	t3 AS (
		SELECT 
			FYear,
			AuctionQuarter,
			GardenMDM,
			Total_Sold_Qty,
			Total_Value,
			Avg_Value_Per_Unit,
			
			CASE WHEN  Total_Sold_Qty > 10000 THEN DENSE_RANK() OVER (PARTITION BY concat(FYear,AuctionQuarter) ORDER BY IF(Total_Sold_Qty > 10000, Avg_Value_Per_Unit,0) DESC) ELSE 0 END AS Rank
		FROM t2
	)
	SELECT * FROM t3 WHERE Rank >= 0;



--------------------------------------------------------------
PRICE LEVELS
--------------------------------------------------------------

with t1 as
(SELECT 
Case when CAST(substring(FinYear,1,4) as INT64) = Season then Season else 0 end as FYear,
GardenMDM,GradeMDM,Subcategory,
SubTeaType,
Case When SubTeaType="SECONDARY" Then SubTeaType Else Subcategory End as SubcategoryAllies,

coalesce(sum(IF(LotStatus = 'Sold',TotalWeight,InvoiceWeight)),0) as Offer_Qty,
sum(TotalWeight) as Sold_Qty,
coalesce(sum(Value),0) as Total_Value

FROM data-warehousing-prod.EasyReports.SaleTransactionView

WHERE
    Season IN (2023,2024) and EstBlf IN ("EST") and Area IN ("AS") and Category IN ("CTC") and Centre IN ("KOL","GUW") and 
    if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 and 56
GROUP BY  FYear, GardenMDM, Subcategory,SubTeaType,GradeMDM,SubcategoryAllies
Having FYear <> 0),

t2 AS (SELECT 
Case when CAST(substring(FinYear,1,4) as INT64) = Season then Season else 0 end as FYear,
coalesce(GardenMDM,"") as GardenMDM,
coalesce( ROUND(sum(Value),0),0) as Total_Value,
coalesce(ROUND(sum(TotalWeight),0),0) as Sold_Qty,
CASE 
    WHEN sum(TotalWeight) >=100000 then dense_rank() OVER (order by if(sum(TotalWeight) >=100000,SUM(Value) / SUM(TotalWeight),0) DESC) else 0 end as BOP

FROM data-warehousing-prod.EasyReports.SaleTransactionView

WHERE 
  Area IN("AS") AND Category = "CTC" and EstBlf IN ("EST") AND Centre IN("KOL","GUW") AND if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 56 AND Season between 2023 and 2024
  
GROUP BY 
FinYear,Season, FYear, GardenMDM

HAVING 
sum(TotalWeight)>0.0001 and FYear !=0)

select t1.FYear, t1.GardenMDM, t1.GradeMDM, t1.Subcategory, t1.SubTeaType, t1.SubcategoryAllies, 
t1.Offer_Qty, t1.Sold_Qty, t1.Total_Value, t2.BOP,
Case 
When t2.BOP Between 1 AND 20 Then "'1-20"
When t2.BOP Between 21 AND 50 Then "21-50"
When t2.BOP Between 51 AND 100 Then "51-100"
When t2.BOP Between 101 AND 150 Then "101-150"
When t2.BOP Between 151 AND 200 Then "151-200"
When t2.BOP >=201  Then "201+"
Else "" End as BOP_Range

 from t1 left join t2 on t1.FYear = t2.FYear and t1.GardenMDM = t2.GardenMDM
 


	
--------------------------------------------------------------
PARCON BUYER GROUP WORKING TABLE
--------------------------------------------------------------

With t1 as
(SELECT
    Case when CAST(substring(FinYear,1,4) as INT64) = Season then Season else 0 end as FYear,
coalesce(GardenMDM,"") as GardenID,

Case
When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 65 AND Season = 2024
AND BuyerMDM="TATA CONSUMER PRODUCTS LIMITED" AND Centre IN("KOL","GUW","SIL") AND TeaType IN ("LEAF","DUST") Then 'TATA CONSUMER PRODUCTS LTD. [GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 65 AND Season = 2024
AND BuyerMDM="THE TELOIJAN TEA CO LTD" AND Centre IN("KOL","GUW") AND TeaType IN ("LEAF","DUST") Then 'TATA CONSUMER PRODUCTS LTD. [GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 65 AND Season = 2024
AND BuyerMDM="WEST BENGAL MANUFACTURING CO PVT LTD" AND Centre IN("KOL","GUW","SIL") AND TeaType IN ("LEAF","DUST") Then 'TATA CONSUMER PRODUCTS LTD. [GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 65 AND Season = 2024
AND BuyerMDM="SB PLANTATIONS PRIVATE LIMITED" AND Centre IN("GUW") AND TeaType IN ("LEAF","DUST") Then 'TATA CONSUMER PRODUCTS LTD. [GROUP]'


When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 30 AND 49 AND Season = 2024
AND BuyerMDM="THE TELOIJAN TEA CO LTD" AND Centre IN("SIL") AND TeaType IN ("LEAF","DUST") Then 'TATA CONSUMER PRODUCTS LTD. [GROUP]'


When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 65 AND Season = 2024
AND BuyerMDM="HINDUSTAN UNILEVER LTD" AND Centre IN("KOL","GUW","SIL") AND TeaType IN ("LEAF","DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 65 AND Season = 2024
AND BuyerMDM="PRANJIVAN J SHAH" AND Centre IN("KOL","GUW","SIL") AND TeaType IN ("LEAF","DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 45 AND 45 AND Season = 2024
AND BuyerMDM="HINDUSTAN TEA EXPORTERS" AND Centre IN("KOL") AND TeaType IN ("LEAF","DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 49 AND 49 AND Season = 2024
AND BuyerMDM="HINDUSTAN TEA EXPORTERS" AND Centre IN("KOL") AND TeaType IN ("DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 50 AND 50 AND Season = 2024
AND BuyerMDM="HINDUSTAN TEA EXPORTERS" AND Centre IN("KOL") AND TeaType IN ("LEAF") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 46 AND 46 AND Season = 2024 
AND BuyerMDM="GLENRICH INTERNATIONAL" AND Centre IN("KOL") AND TeaType IN ("LEAF") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 46 AND 46 AND Season = 2024
AND BuyerMDM="H T EXPORTS" AND Centre IN("KOL") AND TeaType IN ("DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 49 AND 49 AND Season = 2024
AND BuyerMDM="H T EXPORTS" AND Centre IN("KOL") AND TeaType IN ("DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 47 AND 47 AND Season = 2024 
AND BuyerMDM="C I LIMITED" AND Centre IN("KOL") AND TeaType IN ("LEAF","DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 48 AND 48 AND Season = 2024 
AND BuyerMDM="COMMODITIES INTERNATIONAL PRIVATE LIMITED" AND Centre IN("KOL") AND TeaType IN ("LEAF","DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 50 AND 50 AND Season = 2024 
AND BuyerMDM="PRAVIN KUMAR PAWAN KUMAR" AND Centre IN("KOL") AND TeaType IN ("DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 52 AND 52 AND Season = 2024 
AND BuyerMDM="CANARY TEA EXPORTS PRIVATE LIMITED" AND Centre IN("KOL") AND TeaType IN ("LEAF","DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 50 AND 50 AND Season = 2024
AND BuyerMDM="PRAVIN KUMAR PAWAN KUMAR" AND Centre IN("GUW") AND TeaType IN ("LEAF","DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 45 AND 50 AND Season = 2024
AND BuyerMDM="PRANJIVAN J SHAH" AND Centre IN("SIL") AND TeaType IN ("LEAF","DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 50 AND 50 AND Season = 2024 
AND BuyerMDM="PRAVIN KUMAR PAWAN KUMAR" AND Centre IN("SIL") AND TeaType IN ("LEAF","DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'


When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 65 AND Season = 2023
AND BuyerMDM="TATA CONSUMER PRODUCTS LIMITED" AND Centre IN("KOL","GUW","SIL") AND TeaType IN ("LEAF","DUST") Then 'TATA CONSUMER PRODUCTS LTD. [GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 65 AND Season = 2023
AND BuyerMDM="THE TELOIJAN TEA CO LTD" AND Centre IN("KOL","GUW","SIL") AND TeaType IN ("LEAF","DUST") Then 'TATA CONSUMER PRODUCTS LTD. [GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 65 AND Season = 2023
AND BuyerMDM="WEST BENGAL MANUFACTURING CO PVT LTD" AND Centre IN("KOL","GUW","SIL") AND TeaType IN ("LEAF","DUST") Then 'TATA CONSUMER PRODUCTS LTD. [GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 65 AND Season = 2023
AND BuyerMDM="SB PLANTATIONS PRIVATE LIMITED" AND Centre IN("GUW") AND TeaType IN ("LEAF","DUST") Then 'TATA CONSUMER PRODUCTS LTD. [GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 65 AND Season = 2023
AND BuyerMDM="HINDUSTAN UNILEVER LTD" AND Centre IN("KOL","GUW","SIL") AND TeaType IN ("LEAF","DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

When if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 65 AND Season = 2023
AND BuyerMDM="PRANJIVAN J SHAH" AND Centre IN("KOL","GUW","SIL") AND TeaType IN ("LEAF","DUST") Then 'HINDUSTHAN UNILEVER LIMITED[GROUP]'

Else BuyerMDM End As BuyerMDM,

GradeMDM, Centre, SaleNo, SellerGroup, GardenMDM, BrokerCode,

coalesce(SUM(Value)) AS Total_Value,

coalesce(SUM(TotalWeight)) as Sold_Qty

FROM data-warehousing-prod.EasyReports.SaleTransactionView
    
Where Area IN ("DO","TR") and Category = "CTC" and EstBlf ="EST" AND Centre IN("KOL","SIL") AND 

if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) between 14 AND 58 AND Season BETWEEN 2023 AND 2024
	
GROUP BY FYear,GardenID,BuyerMDM,GradeMDM,SaleNo,SellerGroup,BrokerCode,GardenMDM,Centre
HAVING sum(TotalWeight)> 0.001),

t2 as
(SELECT Centre,BuyerID,Buyer,BuyerGroup

from `data-warehousing-prod.EasyReports.Parcon-BuyerGroup`

where Centre IN ("KOL","SIL")),

main_table as(
Select t1.FYear,t1.GardenMDM,

CASE 
	WHEN t2.BuyerGroup IS NULL OR t2.BuyerGroup = '' THEN t1.BuyerMDM 
	ELSE t2.BuyerGroup 
    END AS BuyerGroup,
t1.Sold_Qty, t1.Total_Value

from t1 Left Join t2 ON t1.BuyerMDM = t2.Buyer and t1.Centre = t2.Centre)
 
SELECT 
	FYear,
	GardenMDM,
    BuyerGroup,
    SUM(Total_Value) AS Total_Value,
    SUM(Sold_Qty) AS Sold_Qty,
    
	SUM(Total_Value) / NULLIF(SUM(Sold_Qty), 0) AS AvgPrice,
	
case when sum(Sold_Qty)>=1000 then dense_rank() OVER (Partition By CONCAT(FYear,GardenMDM) order by 
if(sum(Sold_Qty)>=1000, SUM(Total_Value)/SUM(Sold_Qty),0) DESC) else 0 end AS BOP

FROM main_table WHERE Sold_Qty > 0.0001 And GardenMDM IN ("GAIRKHATA") 

GROUP BY BuyerGroup,FYear,GardenMDM Having FYear<>0; 



--------------------------------------------------------------
TC_Tasting
--------------------------------------------------------------

SELECT * 

FROM 

data-warehousing-prod.EasyReports.TC_Tasting

--------------------------------------------------------------
TC_Tasting_WORKING TABLE
--------------------------------------------------------------

With t1 as(
SELECT Location, Tasting_Type, Mark, Invoice, Grade, Category, Sub_Category, Tea_Type, Sub_Tea_Type, Mfg_Date, GP_Date,Tasting_Values, Total_Tasting_Points, Comments, Lot_No, Qty, Season, Sold_Sale_No, Sold_Price,

SAFE_CAST(TRIM(SPLIT(REGEXP_REPLACE(Tasting_Values, r',\s*$', ''), ',')[SAFE_OFFSET(0)]) AS FLOAT64) AS Leaf,
SAFE_CAST(TRIM(SPLIT(REGEXP_REPLACE(Tasting_Values, r',\s*$', ''), ',')[SAFE_OFFSET(1)]) AS FLOAT64) AS Infusion,
SAFE_CAST(TRIM(SPLIT(REGEXP_REPLACE(Tasting_Values, r',\s*$', ''), ',')[SAFE_OFFSET(2)]) AS FLOAT64) AS Liquor

FROM data-warehousing-prod.EasyReports.TC_Tasting

Where Season IN (2025) And Tasting_Type IN ("Muster Tasting","Auction Tasting"))

Select Location, Tasting_Type, Mark, Invoice, Grade, Category, Sub_Category, Tea_Type, Sub_Tea_Type, Mfg_Date, GP_Date,

Tasting_Values, Comments, Lot_No, Season, Sold_Sale_No, Sold_Price,

SUM(Qty) as Qty,
SUM(Leaf) as Leaf,
SUM(Infusion) as Infusion,
SUM(Liquor) as Liquor,
SUM(Total_Tasting_Points) as Total_Tasting_Points,

SUM(Qty)*SUM(Leaf) as WLeaf,
SUM(Qty)*SUM(Infusion) as WInfusion,
SUM(Qty)*SUM(Liquor) as WLiquor,
SUM(Qty)*SUM(Total_Tasting_Points) as WOverall

From t1

Group By Location, Tasting_Type, Mark, Invoice, Grade, Category, Sub_Category, Tea_Type, Sub_Tea_Type, Mfg_Date, GP_Date, Tasting_Values, Comments, Lot_No, Season, Sold_Sale_No, Sold_Price




--------------------------------------------------------------
Parcon-Caller_WORKING TABLE
--------------------------------------------------------------
with t1 as(
SELECT
Case when CAST(substring(FinYear,1,4) as INT64) = Season then Season else 0 end as FYear,
CASE 
WHEN Area = "AS" AND Centre IN ("KOL", "GUW") THEN "AS"
WHEN Area IN ("DO", "TR") AND Centre IN ("KOL", "SIL") THEN "DO/TR"
WHEN Area IN ("CA", "TP") AND Centre IN ("KOL", "GUW") THEN "CA/TP" ELSE ""
END AS AreaAlies,
Centre,Category,SellerGroup,MarkID,GardenMDM,MDMCaller,MDMSubCaller,

sum(TotalWeight) as Sold_Qty,
coalesce(sum(Value),0) as Total_Value

FROM data-warehousing-prod.EasyReports.SaleTransactionView

Where Season IN (2025) And Area IN ("AS","DO","TR","CA","TP") And Category IN ("CTC","ORTHODOX") And if(SaleNo>=1 AND SaleNo<=13,52+SaleNo,SaleNo) Between 14 and 45
And BrokerCode IN ("PC") AND Centre NOT IN ("JAL")

Group By FYear,AreaAlies,Centre,Category,SellerGroup,MarkID,GardenMDM,MDMCaller,MDMSubCaller

Having FYear<>0),

t2 as(Select * FROM data-warehousing-prod.EasyReports.Parcon-Caller)

Select t1.FYear,t1.AreaAlies,t1.Centre,t1.Category,t1.SellerGroup,t1.MarkID,t1.GardenMDM,t1.MDMCaller,t1.MDMSubCaller,

SUM(t2.BudgetedQty) as BudgetedQty,
SUM(t1.Sold_Qty) as Sold_Qty,
SUM(t1.Total_Value) as Total_Value

from t1 Left Join t2 ON t1.MarkID = t2.MarkID And t1.Centre = t2.Centre

Group By t1.FYear,t1.AreaAlies,t1.Category,t1.SellerGroup,t1.MarkID,t1.GardenMDM,t1.MDMCaller,t1.MDMSubCaller,t1.Centre




--------------------------------------------------------------
CREATING WORKING TABLE PRIVATE SALE
--------------------------------------------------------------
SELECT * FROM 

data-warehousing-prod.EasyReports.TC_Privatesale



--------------------------------------------------------------
CREATING WORKING CropBGSG
--------------------------------------------------------------
SELECT * FROM 

data-warehousing-prod.EasyReports.CropBGSG



--------------------------------------------------------------
CREATING WORKING CropCategoryTB
--------------------------------------------------------------
SELECT * FROM 

data-warehousing-prod.EasyReports.CropCategoryTB
