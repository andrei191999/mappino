# Schematron Rules

This directory contains compiled Schematron rules (XSLT format) for business rule validation.

## Required Files

| Profile | File | Source |
|---------|------|--------|
| `peppol-bis3` | `peppol-bis3.xslt` | [Peppol BIS 3.0](https://github.com/OpenPeppol/peppol-bis-invoice-3) |
| `en16931-ubl` | `en16931-ubl.xslt` | [CEN TC 434](https://github.com/ConnectingEurope/eInvoicing-EN16931) |
| `en16931-cii` | `en16931-cii.xslt` | [CEN TC 434](https://github.com/ConnectingEurope/eInvoicing-EN16931) |

## Getting Schematron Files

### Peppol BIS 3.0

```bash
# Clone Peppol BIS repository
git clone https://github.com/OpenPeppol/peppol-bis-invoice-3.git
# Copy compiled XSLT
cp peppol-bis-invoice-3/rules/sch/*/output/*.xslt .
```

### EN 16931 (CEN)

```bash
# Clone CEN eInvoicing repository
git clone https://github.com/ConnectingEurope/eInvoicing-EN16931.git
# Copy compiled schematron XSLTs
cp eInvoicing-EN16931/ubl/xslt/*.xslt .
cp eInvoicing-EN16931/cii/xslt/*.xslt .
```

## File Format

The validator expects pre-compiled XSLT files that produce SVRL (Schematron Validation Report Language) output.

If you have raw `.sch` files, compile them first:

```bash
# Using Saxon or similar XSLT processor
# Compile .sch to .xslt using iso_svrl_for_xslt2.xsl
```

## Auto-Detection

The validator auto-detects which rules to apply based on document namespace:

| Namespace | Profile |
|-----------|---------|
| `urn:oasis:names:specification:ubl:schema:xsd:Invoice-2` | `peppol-bis3` |
| `urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2` | `peppol-bis3` |
| `urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100` | `en16931-cii` |
