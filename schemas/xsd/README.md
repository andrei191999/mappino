# XSD Schemas

This directory contains XSD schemas for XML validation.

## UBL 2.1 Schemas

Download from OASIS: https://docs.oasis-open.org/ubl/os-UBL-2.1/UBL-2.1.zip

Required files for invoice validation:
- `UBL-Invoice-2.1.xsd`
- `UBL-CreditNote-2.1.xsd`

### Quick Setup

```bash
# Download and extract UBL schemas
curl -L -o ubl.zip https://docs.oasis-open.org/ubl/os-UBL-2.1/UBL-2.1.zip
unzip ubl.zip -d ubl-temp
cp ubl-temp/xsd/maindoc/*.xsd .
cp -r ubl-temp/xsd/common .
rm -rf ubl.zip ubl-temp
```

### Directory Structure After Setup

```
schemas/xsd/
├── common/                    # UBL common schemas
│   ├── UBL-CommonAggregateComponents-2.1.xsd
│   ├── UBL-CommonBasicComponents-2.1.xsd
│   └── ...
├── UBL-Invoice-2.1.xsd       # Main invoice schema
├── UBL-CreditNote-2.1.xsd    # Credit note schema
└── README.md
```

## Namespace Mappings

The XSD validator auto-detects schemas by namespace:

| Namespace | Schema File |
|-----------|-------------|
| `urn:oasis:names:specification:ubl:schema:xsd:Invoice-2` | `UBL-Invoice-2.1.xsd` |
| `urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2` | `UBL-CreditNote-2.1.xsd` |
