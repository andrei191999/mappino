<?xml version="1.0" encoding="UTF-8"?>
<!--
  Vasco – Intermediary XML ➜ Peppol BIS 3.0 (Invoice & CreditNote)
  v0.4 — XSL‑T 1.0 compliant (2025‑06‑30)
  • Invoice vs CreditNote selected via InvoiceHeader/MessageType (INV / CRN)
  • Endpoint‑ID scheme:
        • 0088 if PartnerIDType='EAN' and length()=13
        • 9925 BE‑VAT, 9944 NL‑VAT, 9930 DE‑VAT when PartnerIDType='VAT'
  • If Buyer (BY) empty → use Invoicee (IV) block
  • Credit‑notes: positive qty/line‑totals, **negative unit‑price only**
  • Zero‑price lines → 100 % AllowanceCharge (ChargeIndicator=false)
  • Multi‑rate VAT supported (loops over VATCharge)
  • Omits empty optional elements (OrderReference, Delivery, etc.)
  • PaymentMeans (code 30) when IBAN present
  • Currency/UnitCode populated everywhere
  • Fully XSLT 1.0 – no XPath 2.0 functions, AVT ternaries or *abs()*
-->
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" exclude-result-prefixes="xsl">
	<xsl:output method="xml" version="1.0" encoding="UTF-8" indent="yes"/>
	<!-- ===== Helpers =================================================== -->
	<xsl:template name="scheme-from-partner">
		<xsl:param name="p"/>
		<xsl:choose>
			<xsl:when test="$p/PartnerIDType='EAN' and string-length($p/PartnerID)=13">0088</xsl:when>
			<xsl:when test="$p/PartnerIDType='VAT' and $p/Country='BE'">9925</xsl:when>
			<xsl:when test="$p/PartnerIDType='VAT' and $p/Country='NL'">9944</xsl:when>
			<xsl:when test="$p/PartnerIDType='VAT' and $p/Country='DE'">9930</xsl:when>
			<xsl:otherwise>0088</xsl:otherwise>
		</xsl:choose>
	</xsl:template>
	<xsl:template name="fmt-date">
		<xsl:param name="d"/>
		<xsl:value-of select="substring($d,1,4)"/>-<xsl:value-of select="substring($d,5,2)"/>-<xsl:value-of select="substring($d,7,2)"/>
	</xsl:template>
	<!-- numeric formatting -->
	<xsl:template name="fmt-amt">
		<xsl:param name="a"/>
		<xsl:param name="dec" select="2"/>
		<xsl:variable name="isCredit" select="/Document/Invoice/InvoiceHeader/MessageType='CRN'"/>
		<!-- a string of six zeros for building the pow -->
		<xsl:variable name="zeros" select="'000000'"/>
		<!-- a string of six hashes for the format mask -->
		<xsl:variable name="hashes" select="'######'"/>
		<!-- pow = 10^$dec, by concatenating “1” + the first $dec zeros -->
		<xsl:variable name="pow" select="number(concat('1', substring($zeros, 1, $dec)))"/>
		<!-- rounded value as a number -->
		<xsl:variable name="rnd" select="round(number($a) * $pow) div $pow"/>
		<!-- mask like “0.##” or “0.######” -->
		<xsl:variable name="mask" select="concat('0.', substring($hashes, 1, $dec))"/>
		<!-- format it, then remove any “-” -->
		<xsl:choose>
			<xsl:when test="$isCredit and $a &lt; 0">
				<xsl:value-of select="translate(format-number($rnd, $mask), '-', '')"/>
			</xsl:when>
			<xsl:otherwise>
				<xsl:value-of select="format-number($rnd, $mask)"/>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:message>isCredit <xsl:value-of select="$isCredit"/></xsl:message>
		<xsl:message>a <xsl:value-of select="$a"/></xsl:message>
		
	</xsl:template>
	<!-- map raw unit to a valid UN/ECE Rec 20 code -->
	<xsl:template name="map-unit">
		<xsl:param name="u"/>
		<xsl:variable name="U" select="translate(normalize-space($u),
        'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ')"/>
		<xsl:choose>
			<!-- stuk/piece -->
			<xsl:when test="$U='ST'">C62</xsl:when>
			<!-- roll -->
			<xsl:when test="$U='ROL'">NAR</xsl:when>
			<!-- pack -->
			<xsl:when test="$U='PK'">NMP</xsl:when>
			<!-- piece -->
			<xsl:when test="$U='PCE'">H87</xsl:when>
			<xsl:otherwise>
				<xsl:value-of select="$U"/>
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>
	<xsl:template name="round2">
		<xsl:param name="n"/>
		<xsl:value-of select="round($n * 100) div 100"/>
	</xsl:template>
	<!-- decide the monetary value of the allowance/charge -->
	<xsl:template name="calc-disc">
		<xsl:param name="ac"/>
		<!-- current AllowanceCharge node -->
		<xsl:variable name="calc" select="number(../../CustomAddendum/LineDiscAmtCalculated)"/>
		<xsl:variable name="qty" select="number(translate(string(../../Quantities/Quantity[QuantityType='INV']/Amount),'-',''))"/>
		<!--<xsl:message>calc<xsl:value-of select="$calc"/>
		</xsl:message>
		<xsl:message>qty<xsl:value-of select="$qty"/>
		</xsl:message>-->
		<xsl:choose>
			<!-- (a) explicit LineDiscAmtCalculated -->
			<xsl:when test="$calc != 0 and $calc != NaN">
				<xsl:call-template name="round2">
					<xsl:with-param name="n" select="$calc"/>
				</xsl:call-template>
			</xsl:when>
			<!-- (b) derive from base × % -->
			<xsl:otherwise>
				<xsl:variable name="base" select="number($ac/BasisAmount * $qty)"/>
				<xsl:variable name="pct" select="number($ac/Percentage)"/>
				<xsl:call-template name="round2">
					<xsl:with-param name="n" select="($base * $pct) div 100"/>
				</xsl:call-template>
				<!--<xsl:message>base<xsl:value-of select="$base"/>
				</xsl:message>
				<xsl:message>pct<xsl:value-of select="$pct"/>
				</xsl:message>-->
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>
	<!-- ===== Root switch =============================================== -->
	<xsl:template match="/Document">
		<xsl:variable name="isCredit" select="Invoice/InvoiceHeader/MessageType='CRN'"/>
		<xsl:choose>
			<xsl:when test="$isCredit">
				<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
					<xsl:apply-templates select="." mode="main">
						<xsl:with-param name="isCredit" select="$isCredit"/>
					</xsl:apply-templates>
				</CreditNote>
			</xsl:when>
			<xsl:otherwise>
				<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
					<xsl:apply-templates select="." mode="main">
						<xsl:with-param name="isCredit" select="$isCredit"/>
					</xsl:apply-templates>
				</Invoice>
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>
	<!-- ===== Main body ================================================= -->
	<xsl:template match="Document" mode="main">
		<xsl:param name="isCredit"/>
		<!-- partner nodes -->
		<xsl:variable name="su" select="Invoice/InvoiceHeader/Partners/Partner[PartnerType='SU']"/>
		<xsl:variable name="byRaw" select="Invoice/InvoiceHeader/Partners/Partner[PartnerType='BY']"/>
		<xsl:variable name="iv" select="Invoice/InvoiceHeader/Partners/Partner[PartnerType='IV']"/>
		<xsl:variable name="by" select="( $byRaw[normalize-space(PartnerID) or normalize-space(Name)] | $iv[not(normalize-space($byRaw/PartnerID) or normalize-space($byRaw/Name))] )[1]"/>
		<xsl:variable name="currency" select="Invoice/InvoiceHeader/InvoiceCurrency"/>
		<xsl:variable name="docRate" select="number(Invoice/InvoiceTotals/TotalVATCharges/VATCharge[1]/Rate)"/>
		<xsl:variable name="refPOR" select="Invoice/InvoiceHeader/References/Reference[ReferenceType='POR']"/>
		<xsl:variable name="refVOR" select="Invoice/InvoiceHeader/References/Reference[ReferenceType='VOR']"/>
		<xsl:variable name="refDSP" select="Invoice/InvoiceHeader/References/Reference[ReferenceType='DSP']"/>
		<xsl:variable name="refSIN" select="Invoice/InvoiceHeader/References/Reference[ReferenceType='SIN']"/>
		<xsl:variable name="refDON" select="Invoice/InvoiceHeader/References/Reference[ReferenceType='DON']"/>
		<!-- ===== Header ===== -->
		<cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0</cbc:CustomizationID>
		<cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>
		<cbc:ID>
			<xsl:value-of select="DocumentNumber"/>
		</cbc:ID>
		<cbc:IssueDate>
			<xsl:call-template name="fmt-date">
				<xsl:with-param name="d" select="Invoice/InvoiceHeader/Dates/InvoiceDate"/>
			</xsl:call-template>
		</cbc:IssueDate>
		<xsl:choose>
			<xsl:when test="$isCredit">
				<cbc:CreditNoteTypeCode>381</cbc:CreditNoteTypeCode>
			</xsl:when>
			<xsl:otherwise>
				<cbc:DueDate>
					<xsl:call-template name="fmt-date">
						<xsl:with-param name="d" select="Invoice/InvoiceHeader/Dates/DueDate"/>
					</xsl:call-template>
				</cbc:DueDate>
				<cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
			</xsl:otherwise>
		</xsl:choose>
		<cbc:DocumentCurrencyCode>
			<xsl:value-of select="$currency"/>
		</cbc:DocumentCurrencyCode>
		<cbc:BuyerReference>
			<xsl:choose>
				<!-- BY-party internal reference (ICN) -->
				<xsl:when test="normalize-space($by/PartnerReferences/ReferenceNumber)!=''">
					<xsl:value-of select="normalize-space($by/PartnerReferences/ReferenceNumber)"/>
				</xsl:when>
				<!-- or purchase-order number -->
				<xsl:when test="normalize-space($refPOR/ReferenceNumber)!=''">
					<xsl:value-of select="$refPOR/ReferenceNumber"/>
				</xsl:when>
				<!-- fallback so BT-10 is never empty -->
				<xsl:otherwise>NA</xsl:otherwise>
			</xsl:choose>
		</cbc:BuyerReference>
		<!-- ❷  –– REPLACE the current OrderReference block with the guard below –– -->
		<xsl:if test="normalize-space($refPOR/ReferenceNumber)!=''">
			<cac:OrderReference>
				<cbc:ID>
					<xsl:value-of select="$refPOR/ReferenceNumber"/>
				</cbc:ID>
			</cac:OrderReference>
		</xsl:if>
		<!-- Original invoice when this file is a credit-note -->
		<xsl:if test="$isCredit and normalize-space($refSIN/ReferenceNumber)!=''">
			<cac:BillingReference>
				<cac:InvoiceDocumentReference>
					<cbc:ID>
						<xsl:value-of select="$refSIN/ReferenceNumber"/>
					</cbc:ID>
				</cac:InvoiceDocumentReference>
			</cac:BillingReference>
		</xsl:if>
		<!-- Despatch advice -->
		<xsl:if test="normalize-space($refDSP/ReferenceNumber)!=''">
			<cac:DespatchDocumentReference>
				<cbc:ID>
					<xsl:value-of select="$refDSP/ReferenceNumber"/>
				</cbc:ID>
			</cac:DespatchDocumentReference>
		</xsl:if>
		<!-- Sales/Vendor order -->
		<xsl:if test="normalize-space($refVOR/ReferenceNumber)!=''">
			<cac:AdditionalDocumentReference>
				<cbc:ID>
					<xsl:value-of select="$refVOR/ReferenceNumber"/>
				</cbc:ID>
				<cbc:DocumentType>Sales order</cbc:DocumentType>
			</cac:AdditionalDocumentReference>
		</xsl:if>
		<xsl:if test="normalize-space($refDON/ReferenceNumber)!=''">
			<cac:AdditionalDocumentReference>
				<cbc:ID>
					<xsl:value-of select="$refDON/ReferenceNumber"/>
				</cbc:ID>
				<cbc:DocumentType>Delivery document reference</cbc:DocumentType>
			</cac:AdditionalDocumentReference>
		</xsl:if>
		<!-- ===== Supplier ===== -->
		<cac:AccountingSupplierParty>
			<cac:Party>
				<cbc:EndpointID>
					<xsl:attribute name="schemeID"><xsl:call-template name="scheme-from-partner"><xsl:with-param name="p" select="$su"/></xsl:call-template></xsl:attribute>
					<xsl:value-of select="translate(translate($su/PartnerID,' ',''),'.','')"/>
				</cbc:EndpointID>
				<cac:PartyName>
					<cbc:Name>
						<xsl:value-of select="$su/Name"/>
					</cbc:Name>
				</cac:PartyName>
				<cac:PostalAddress>
					<cbc:StreetName>
						<xsl:value-of select="$su/StreetName"/>
					</cbc:StreetName>
					<cbc:CityName>
						<xsl:value-of select="$su/City"/>
					</cbc:CityName>
					<cbc:PostalZone>
						<xsl:value-of select="$su/PostalCode"/>
					</cbc:PostalZone>
					<cac:Country>
						<cbc:IdentificationCode>
							<xsl:value-of select="$su/Country"/>
						</cbc:IdentificationCode>
					</cac:Country>
				</cac:PostalAddress>
				<cac:PartyTaxScheme>
					<cbc:CompanyID>
						<xsl:value-of select="translate($su/VATNumber,' ', '')"/>
					</cbc:CompanyID>
					<cac:TaxScheme>
						<cbc:ID>VAT</cbc:ID>
					</cac:TaxScheme>
				</cac:PartyTaxScheme>
				<cac:PartyLegalEntity>
					<cbc:RegistrationName>
						<xsl:value-of select="$su/Name"/>
					</cbc:RegistrationName>
					<cbc:CompanyID>
						<xsl:value-of select="translate($su/PartnerID,' ','')"/>
					</cbc:CompanyID>
				</cac:PartyLegalEntity>
			</cac:Party>
		</cac:AccountingSupplierParty>
		<!-- ===== Buyer ===== -->
		<cac:AccountingCustomerParty>
			<cac:Party>
				<cbc:EndpointID>
					<xsl:attribute name="schemeID"><xsl:call-template name="scheme-from-partner"><xsl:with-param name="p" select="$by"/></xsl:call-template></xsl:attribute>
					<xsl:value-of select="translate(translate($by/PartnerID,' ',''),'.','')"/>
				</cbc:EndpointID>
				<cac:PartyName>
					<cbc:Name>
						<xsl:value-of select="$by/Name"/>
					</cbc:Name>
				</cac:PartyName>
				<cac:PostalAddress>
					<cbc:StreetName>
						<xsl:value-of select="$by/StreetName"/>
					</cbc:StreetName>
					<cbc:CityName>
						<xsl:value-of select="$by/City"/>
					</cbc:CityName>
					<cbc:PostalZone>
						<xsl:value-of select="$by/PostalCode"/>
					</cbc:PostalZone>
					<cac:Country>
						<cbc:IdentificationCode>
							<xsl:value-of select="$by/Country"/>
						</cbc:IdentificationCode>
					</cac:Country>
				</cac:PostalAddress>
				<cac:PartyTaxScheme>
					<cbc:CompanyID>
						<xsl:value-of select="translate($by/VATNumber,' ', '')"/>
					</cbc:CompanyID>
					<cac:TaxScheme>
						<cbc:ID>VAT</cbc:ID>
					</cac:TaxScheme>
				</cac:PartyTaxScheme>
				<cac:PartyLegalEntity>
					<cbc:RegistrationName>
						<xsl:value-of select="$by/Name"/>
					</cbc:RegistrationName>
					<cbc:CompanyID>
						<xsl:value-of select="translate($by/PartnerID,' ','')"/>
					</cbc:CompanyID>
				</cac:PartyLegalEntity>
			</cac:Party>
		</cac:AccountingCustomerParty>
		<!-- ===== Payment Means (if IBAN) ===== -->
		<xsl:if test="$su/FinancialInstitution[InstitutionIDType='IBAN']/AccountHolderNumber">
			<cac:PaymentMeans>
				<cbc:PaymentMeansCode>30</cbc:PaymentMeansCode>
				<cac:PayeeFinancialAccount>
					<cbc:ID schemeID="IBAN">
						<xsl:value-of select="translate($su/FinancialInstitution[InstitutionIDType='IBAN']/AccountHolderNumber,' ','')"/>
					</cbc:ID>
					<cac:FinancialInstitutionBranch>
						<cac:FinancialInstitution>
							<cbc:ID schemeID="BIC">
								<xsl:value-of select="$su/FinancialInstitution[InstitutionIDType='SWIFT']/AccountHolderNumber"/>
							</cbc:ID>
						</cac:FinancialInstitution>
					</cac:FinancialInstitutionBranch>
				</cac:PayeeFinancialAccount>
			</cac:PaymentMeans>
		</xsl:if>
		<!-- ===== Document level Allowance / Charge (if present) ===== -->
		<xsl:for-each select="Invoice/InvoiceHeader/PaymentTerms[number(Amount) != 0]">
			<cac:AllowanceCharge>
				<cbc:ChargeIndicator>
					<xsl:choose>
						<xsl:when test="PaymentType='CHG'">true</xsl:when>
						<xsl:otherwise>false</xsl:otherwise>
					</xsl:choose>
				</cbc:ChargeIndicator>
				<xsl:if test="normalize-space(AdditionalPaymentInformation)">
					<cbc:AllowanceChargeReason>
						<xsl:value-of select="AdditionalPaymentInformation"/>
					</cbc:AllowanceChargeReason>
				</xsl:if>
				<xsl:if test="Percentage != '' and number(Percentage)!=0">
					<cbc:MultiplierFactorNumeric>
						<xsl:call-template name="fmt-amt">
							<xsl:with-param name="a" select="Percentage"/>
						</xsl:call-template>
					</cbc:MultiplierFactorNumeric>
				</xsl:if>
				<cbc:Amount currencyID="{$currency}">
					<xsl:call-template name="fmt-amt">
						<xsl:with-param name="a" select="Amount"/>
					</xsl:call-template>
				</cbc:Amount>
				<xsl:if test="../../InvoiceTotals/TaxableAmountWithoutPaymentDiscount">
					<cbc:BaseAmount currencyID="{$currency}">
						<xsl:call-template name="fmt-amt">
							<xsl:with-param name="a" select="../../InvoiceTotals/TaxableAmountWithoutPaymentDiscount"/>
						</xsl:call-template>
					</cbc:BaseAmount>
				</xsl:if>
				<!--<xsl:message>ratefromAC <xsl:value-of select="VATrate/Rate"/>
				</xsl:message>
				<xsl:message>docRate <xsl:value-of select="$docRate"/>
				</xsl:message>-->
				<cac:TaxCategory>
					<!-- try the rate that came with the AllowanceCharge -->
					<xsl:variable name="rateFromAC" select="number(VATrate/Rate)"/>
					<!-- if none, look at all VAT charges in the header -->
					<!-- pick one -->
					<xsl:variable name="useRate">
						<xsl:choose>
							<xsl:when test="$rateFromAC != 0 and string-length(VATrate/Rate)">
								<xsl:value-of select="$rateFromAC"/>
							</xsl:when>
							<xsl:otherwise>
								<xsl:value-of select="$docRate"/>
							</xsl:otherwise>
						</xsl:choose>
					</xsl:variable>
					<!-- VAT category code -->
					<cbc:ID>
						<xsl:choose>
							<xsl:when test="$useRate = 0">E</xsl:when>
							<xsl:otherwise>S</xsl:otherwise>
						</xsl:choose>
					</cbc:ID>
					<!-- VAT percentage -->
					<cbc:Percent>
						<xsl:value-of select="$useRate"/>
					</cbc:Percent>
					<!-- exemption reason only when you really output 0 % -->
					<xsl:if test="$useRate = 0">
						<cbc:TaxExemptionReason>Document level discount – VAT exempt</cbc:TaxExemptionReason>
					</xsl:if>
					<cac:TaxScheme>
						<cbc:ID>VAT</cbc:ID>
					</cac:TaxScheme>
				</cac:TaxCategory>
			</cac:AllowanceCharge>
		</xsl:for-each>
		<!-- ===== Tax Totals ===== -->
		<cac:TaxTotal>
			<cbc:TaxAmount currencyID="{$currency}">
				<xsl:call-template name="fmt-amt">
					<xsl:with-param name="a" select="sum(Invoice/InvoiceTotals/TotalVATCharges/VATCharge/TotalVATAmount)"/>
				</xsl:call-template>
			</cbc:TaxAmount>
			<xsl:for-each select="Invoice/InvoiceTotals/TotalVATCharges/VATCharge">
				<cac:TaxSubtotal>
					<cbc:TaxableAmount currencyID="{$currency}">
						<xsl:call-template name="fmt-amt">
							<xsl:with-param name="a" select="TaxableAmountWithPaymentDiscount"/>
						</xsl:call-template>
					</cbc:TaxableAmount>
					<cbc:TaxAmount currencyID="{$currency}">
						<xsl:call-template name="fmt-amt">
							<xsl:with-param name="a" select="TotalVATAmount"/>
						</xsl:call-template>
					</cbc:TaxAmount>
					<cac:TaxCategory>
						<cbc:ID>
							<xsl:choose>
								<xsl:when test="Rate=0">E</xsl:when>
								<xsl:otherwise>S</xsl:otherwise>
							</xsl:choose>
						</cbc:ID>
						<cbc:Percent>
							<xsl:value-of select="Rate"/>
						</cbc:Percent>
						<xsl:if test="Rate=0">
							<cbc:TaxExemptionReason>Exempt from VAT</cbc:TaxExemptionReason>
						</xsl:if>
						<cac:TaxScheme>
							<cbc:ID>VAT</cbc:ID>
						</cac:TaxScheme>
					</cac:TaxCategory>
				</cac:TaxSubtotal>
			</xsl:for-each>
		</cac:TaxTotal>
		<!--<xsl:message>Found <xsl:value-of select="count(Invoice/InvoiceTotals/TotalVATCharges/VATCharge)"/> VATCharge nodes.</xsl:message>-->

		<!-- ===== Monetary Totals ===== -->
		<xsl:variable name="docAllowTotal" select="sum(Invoice/InvoiceHeader/PaymentTerms[PaymentType = 'DIS']/Amount)"/>
		<xsl:variable name="docChargeTotal" select="sum(Invoice/InvoiceHeader/PaymentTerms[PaymentType = 'CHG']/Amount)"/>
		<cac:LegalMonetaryTotal>
			<cbc:LineExtensionAmount currencyID="{$currency}">
				<xsl:call-template name="fmt-amt">
					<xsl:with-param name="a" select="Invoice/InvoiceTotals/TaxableAmountWithoutPaymentDiscount"/>
				</xsl:call-template>
			</cbc:LineExtensionAmount>
			<cbc:TaxExclusiveAmount currencyID="{$currency}">
				<xsl:call-template name="fmt-amt">
					<xsl:with-param name="a" select="Invoice/InvoiceTotals/TaxableAmountWithPaymentDiscount"/>
				</xsl:call-template>
			</cbc:TaxExclusiveAmount>
			<cbc:TaxInclusiveAmount currencyID="{$currency}">
				<xsl:call-template name="fmt-amt">
					<xsl:with-param name="a" select="Invoice/InvoiceTotals/TotalInvoiceAmount"/>
				</xsl:call-template>
			</cbc:TaxInclusiveAmount>
			<xsl:if test="$docAllowTotal != 0">
				<cbc:AllowanceTotalAmount currencyID="{$currency}">
					<xsl:call-template name="fmt-amt">
						<xsl:with-param name="a" select="$docAllowTotal"/>
					</xsl:call-template>
				</cbc:AllowanceTotalAmount>
			</xsl:if>
			<!-- BT-110 – Sum of document-level charges (ex-VAT) -->
			<xsl:if test="$docChargeTotal != 0">
				<cbc:ChargeTotalAmount currencyID="{$currency}">
					<xsl:call-template name="fmt-amt">
						<xsl:with-param name="a" select="$docChargeTotal"/>
					</xsl:call-template>
				</cbc:ChargeTotalAmount>
			</xsl:if>
			<cbc:PayableAmount currencyID="{$currency}">
				<xsl:call-template name="fmt-amt">
					<xsl:with-param name="a" select="Invoice/InvoiceTotals/TotalInvoiceAmount"/>
				</xsl:call-template>
			</cbc:PayableAmount>
		</cac:LegalMonetaryTotal>
		<!-- ===== Lines ===== -->
		<xsl:for-each select="Invoice/InvoiceDetail/InvoiceItem">
			<xsl:choose>
				<xsl:when test="$isCredit">
					<cac:CreditNoteLine>
						<xsl:call-template name="LineCore">
							<xsl:with-param name="isCredit" select="true()"/>
							<xsl:with-param name="currency" select="$currency"/>
						</xsl:call-template>
					</cac:CreditNoteLine>
				</xsl:when>
				<xsl:otherwise>
					<cac:InvoiceLine>
						<xsl:call-template name="LineCore">
							<xsl:with-param name="isCredit" select="false()"/>
							<xsl:with-param name="currency" select="$currency"/>
						</xsl:call-template>
					</cac:InvoiceLine>
				</xsl:otherwise>
			</xsl:choose>
		</xsl:for-each>
	</xsl:template>
	<xsl:template name="LineCore" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
		<xsl:param name="isCredit"/>
		<xsl:param name="currency"/>
		<xsl:variable name="unit">
			<xsl:choose>
				<xsl:when test="normalize-space(Quantities/Quantity[QuantityType='INV']/UnitOfMeasure)">
					<xsl:call-template name="map-unit">
						<xsl:with-param name="u" select="Quantities/Quantity[QuantityType='INV']/UnitOfMeasure"/>
					</xsl:call-template>
				</xsl:when>
				<xsl:otherwise>C62</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<!--<xsl:variable name="qty" select="number(translate(string(Quantities/Quantity[QuantityType='INV']/Amount),'-',''))"/>-->
		<xsl:variable name="qtyRaw" select="number(Quantities/Quantity[QuantityType='INV']/Amount)"/>
		<!-- keep sign for invoices, flip to positive for credit-notes -->
		<xsl:variable name="qty">
			<xsl:choose>
				<xsl:when test="$isCredit and $qtyRaw &lt; 0"><xsl:value-of select="-$qtyRaw"/></xsl:when>
				<xsl:otherwise><xsl:value-of select="$qtyRaw"/></xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<xsl:variable name="basis" select="UnitPriceBasis"/>
		<xsl:variable name="lineNet" select="NetLineAmount"/>
		<xsl:variable name="price" select="AllowanceCharges/AllowanceCharge/BasisAmount * $basis"/>
		<!--<xsl:message>
		  LINE <xsl:value-of select="position()"/>
		  ⇒ qty=<xsl:value-of select="$qty"/>
		  netPrice=<xsl:value-of select="SupplierNetUnitPrice"/>
		  base=<xsl:value-of select="$basis"/>
		  netLine=<xsl:value-of select="$lineNet"/>
		  price=<xsl:value-of select="$price"/>
		</xsl:message>-->
		<!-- identifiers -->
		<cbc:ID>
			<xsl:value-of select="position()"/>
		</cbc:ID>
		<!-- quantity -->
		<xsl:choose>
			<xsl:when test="$isCredit">
				<cbc:CreditedQuantity unitCode="{$unit}">
					<xsl:value-of select="format-number($qty,'#0.00')"/>
				</cbc:CreditedQuantity>
			</xsl:when>
			<xsl:otherwise>
				<cbc:InvoicedQuantity unitCode="{$unit}">
					<xsl:value-of select="format-number($qty,'#0.00')"/>
				</cbc:InvoicedQuantity>
			</xsl:otherwise>
		</xsl:choose>
		<!-- line-extension (always positive) -->
		<cbc:LineExtensionAmount currencyID="{$currency}">
			<xsl:call-template name="fmt-amt">
				<xsl:with-param name="a">
					<xsl:choose>
						<!-- credit-note lines must remain positive -->
						<xsl:when test="$isCredit and number($lineNet) &lt; 0"><xsl:value-of select="-1*$lineNet"/></xsl:when>
						<xsl:otherwise><xsl:value-of select="$lineNet"/></xsl:otherwise>
					</xsl:choose>
				</xsl:with-param>
			</xsl:call-template>
		</cbc:LineExtensionAmount>
		<!-- ========================================================= -->
		<!--      Map every incoming AllowanceCharge block (if any)     -->
		<!--      – we *only* skip it when the resulting amount = 0     -->
		<!--      – Amount = ex-VAT value of the allowance/charge       -->
		<!-- ========================================================= -->
		<xsl:for-each select="AllowanceCharges/AllowanceCharge">
			<!-- work out the monetary value once, using the helper    -->
			<xsl:variable name="thisAmt">
				<xsl:call-template name="calc-disc">
					<xsl:with-param name="ac" select="."/>
				</xsl:call-template>
			</xsl:variable>
			<!--<xsl:message>
				<xsl:value-of select="round($thisAmt * 100)"/>
			</xsl:message>
			<xsl:message>
				<xsl:value-of select="$thisAmt"/>
			</xsl:message>-->
			<!-- create the element unless the *effective* amount is 0 -->
			<xsl:if test="round($thisAmt * 100) != 0">
				<cac:AllowanceCharge>
					<!-- charge = true, discount = false -->
					<cbc:ChargeIndicator>
						<xsl:choose>
							<xsl:when test="ACType = 'CHG'">true</xsl:when>
							<xsl:otherwise>false</xsl:otherwise>
						</xsl:choose>
					</cbc:ChargeIndicator>
					<!-- optional free-text reason -->
					<xsl:if test="normalize-space(Description)">
						<cbc:AllowanceChargeReason>
							<xsl:value-of select="Description"/>
						</cbc:AllowanceChargeReason>
					</xsl:if>
					<!-- percentage – only when it exists *and* ≠ 0  -->
					<xsl:if test="normalize-space(Percentage) and number(Percentage) != 0">
						<cbc:MultiplierFactorNumeric>
							<xsl:call-template name="round2">
								<xsl:with-param name="n" select="Percentage"/>
							</xsl:call-template>
						</cbc:MultiplierFactorNumeric>
					</xsl:if>
					<!-- mandatory ex-VAT amount  -->
					<cbc:Amount currencyID="{$currency}">
						<xsl:call-template name="round2">
							<xsl:with-param name="n" select="$thisAmt"/>
						</xsl:call-template>
					</cbc:Amount>
					<!-- base amount, if the sender supplied one -->
					<xsl:if test="normalize-space(BasisAmount)">
						<cbc:BaseAmount currencyID="{$currency}">
							<xsl:call-template name="round2">
								<xsl:with-param name="n" select="BasisAmount * $qty"/>
							</xsl:call-template>
						</cbc:BaseAmount>
					</xsl:if>
					<!-- VAT classification  -->
					<cac:TaxCategory>
						<cbc:ID>
							<xsl:choose>
								<xsl:when test="VATrate/Rate = 0">E</xsl:when>
								<xsl:otherwise>S</xsl:otherwise>
							</xsl:choose>
						</cbc:ID>
						<cbc:Percent>
							<xsl:value-of select="VATrate/Rate"/>
						</cbc:Percent>
						<cac:TaxScheme>
							<cbc:ID>VAT</cbc:ID>
						</cac:TaxScheme>
					</cac:TaxCategory>
				</cac:AllowanceCharge>
			</xsl:if>
		</xsl:for-each>
		<!-- item -->
		<cac:Item>
			<cbc:Description>
				<xsl:value-of select="LongDescription"/>
			</cbc:Description>
			<cbc:Name>
				<xsl:choose>
					<xsl:when test="normalize-space(SupplierArticleNumber)!=''">
						<xsl:value-of select="SupplierArticleNumber"/>
					</xsl:when>
					<xsl:otherwise>
						<xsl:value-of select="substring(LongDescription,1,80)"/>
					</xsl:otherwise>
				</xsl:choose>
			</cbc:Name>
			<cac:ClassifiedTaxCategory>
				<cbc:ID>
					<xsl:choose>
						<xsl:when test="VATCharges/VATCharge/Rate=0">E</xsl:when>
						<xsl:otherwise>S</xsl:otherwise>
					</xsl:choose>
				</cbc:ID>
				<cbc:Percent>
					<xsl:value-of select="VATCharges/VATCharge/Rate"/>
				</cbc:Percent>
				<cac:TaxScheme>
					<cbc:ID>VAT</cbc:ID>
				</cac:TaxScheme>
			</cac:ClassifiedTaxCategory>
		</cac:Item>
		<!-- price (BT-146 must be ≥0) -->
		<cac:Price>
			<cbc:PriceAmount currencyID="{$currency}">
				<xsl:call-template name="fmt-amt">
					<xsl:with-param name="a" select="$price"/>
					<xsl:with-param name="dec" select="6"/>
				</xsl:call-template>
			</cbc:PriceAmount>
			<cbc:BaseQuantity unitCode="{$unit}">
				<xsl:value-of select="format-number($basis,'#0.###')"/>
			</cbc:BaseQuantity>
		</cac:Price>
	</xsl:template>
</xsl:stylesheet>
