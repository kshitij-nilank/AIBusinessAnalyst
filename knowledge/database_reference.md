# Database Reference

## Main Tables Found

### `data-warehousing-prod.EasyReports.SaleTransactionView`
Primary auction transaction table. Use this for most auction sale reports.

Common fields seen:
- FinYear
- Season
- SaleNo
- Area
- Centre
- Category
- TeaType
- SubTeaType
- EstBlf
- GardenMDM
- BuyerMDM
- GradeMDM
- MDMGradeGroup
- LotStatus
- TotalWeight
- InvoiceWeight
- Value
- AuctionDate
- GPDate

### `data-warehousing-prod.EasyReports.TeaMart`
TeaMart table. Use when request specifically needs TeaMart/TM view.

### Other tables found
- `data-warehousing-prod.EasyReports.TI`
- `data-warehousing-prod.EasyReports.TC_Tasting`
- `data-warehousing-prod.EasyReports.TC_Privatesale`
- `data-warehousing-prod.EasyReports.CropBGSG`
- `data-warehousing-prod.EasyReports.CropCategoryTB`
- `data-warehousing-prod.EasyReports.Parcon-BuyerGroup`
- `data-warehousing-prod.EasyReports.Parcon-Caller`
