<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
	<xsl:output method="xml" indent="yes" encoding="UTF-8"/>
	<!-- ===================================================================== -->
	<!-- Helper decimal sum function (supports comma and dot)                  -->
	<!-- ===================================================================== -->
	<xsl:key name="taxByRate" match="E1EDP04" use="MSATZ"/>
	<xsl:template name="sum-decimal">
		<xsl:param name="nodes"/>
		<xsl:param name="pos" select="1"/>
		<xsl:choose>
			<xsl:when test="$pos &gt; count($nodes)">
				<xsl:value-of select="0"/>
			</xsl:when>
			<xsl:otherwise>
				<xsl:variable name="current" select="number(translate($nodes[$pos], ',', '.'))"/>
				<xsl:variable name="rest">
					<xsl:call-template name="sum-decimal">
						<xsl:with-param name="nodes" select="$nodes"/>
						<xsl:with-param name="pos" select="$pos + 1"/>
					</xsl:call-template>
				</xsl:variable>
				<xsl:value-of select="$current + number($rest)"/>
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>
	<!-- ===================================================================== -->
	<!-- ROOT TEMPLATE                                                         -->
	<!-- ===================================================================== -->
	<xsl:template match="/">
		<!-- Header structure -->
		<!-- E1EDK01: Document header general data -->
		<xsl:variable name="k01" select="INVOIC02/IDOC/E1EDK01"/>
		<!-- E1EDK03: Document header date segment. IDDAT=012 (Document Date), IDDAT=024 (Due Date) -->
		<xsl:variable name="headerDateIssueRaw" select="INVOIC02/IDOC/E1EDK03[IDDAT='012']/DATUM"/>
		<xsl:variable name="headerDateDueRaw" select="INVOIC02/IDOC/E1EDK03[IDDAT='024']/DATUM"/>
		<!-- Currency -->
		<xsl:variable name="currency">
			<xsl:choose>
				<xsl:when test="$k01/CURCY != ''">
					<xsl:value-of select="$k01/CURCY"/>
				</xsl:when>
				<xsl:otherwise>EUR</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<!-- Supplier & Customer nodes -->
		<!-- E1EDKA1: Partner Information. PARVW='RS' (Invoicing Party/Supplier), PARVW='BK' (Customer/Buyer) -->
		<xsl:variable name="sup" select="INVOIC02/IDOC/E1EDKA1[PARVW='RS'][1]"/>
		<xsl:variable name="cus" select="INVOIC02/IDOC/E1EDKA1[PARVW='BK'][1]"/>
		<!-- VAT numbers -->
		<xsl:variable name="supVatFull" select="$k01/EIGENUINR"/>
		<xsl:variable name="cusVatFull" select="$k01/KUNDEUINR"/>
		<xsl:variable name="supVat">
			<xsl:choose>
				<xsl:when test="starts-with($supVatFull, 'BE')">
					<xsl:value-of select="substring($supVatFull, 3)"/>
				</xsl:when>
				<xsl:otherwise>
					<xsl:value-of select="$supVatFull"/>
				</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<xsl:variable name="cusVat">
			<xsl:choose>
				<xsl:when test="starts-with($cusVatFull, 'BE')">
					<xsl:value-of select="substring($cusVatFull, 3)"/>
				</xsl:when>
				<xsl:otherwise>
					<xsl:value-of select="$cusVatFull"/>
				</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<!-- Endpoint identification -->
		<!-- Try to get Peppol ID from ZE1EDKA1_EXT extension first, then fallback to EDI_DC40 -->
		<xsl:variable name="supPeppolID" select="$sup/ZE1EDKA1_EXT/PEPPOL_ID"/>
		<xsl:variable name="cusPeppolID" select="$cus/ZE1EDKA1_EXT/PEPPOL_ID"/>

		<xsl:variable name="sndLad" select="INVOIC02/IDOC/EDI_DC40/SNDLAD"/>
		<xsl:variable name="rcvLad" select="INVOIC02/IDOC/EDI_DC40/RCVLAD"/>

		<xsl:variable name="supEndpointScheme">
			<xsl:choose>
				<xsl:when test="$supPeppolID != ''">
					<xsl:value-of select="substring-before($supPeppolID, ':')"/>
				</xsl:when>
				<xsl:otherwise>
					<xsl:value-of select="substring-before($sndLad, ':')"/>
				</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<xsl:variable name="supEndpointValue">
			<xsl:choose>
				<xsl:when test="$supPeppolID != ''">
					<xsl:value-of select="substring-after($supPeppolID, ':')"/>
				</xsl:when>
				<xsl:otherwise>
					<xsl:value-of select="substring-after($sndLad, ':')"/>
				</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>

		<xsl:variable name="cusEndpointScheme">
			<xsl:choose>
				<xsl:when test="$cusPeppolID != ''">
					<xsl:value-of select="substring-before($cusPeppolID, ':')"/>
				</xsl:when>
				<xsl:otherwise>
					<xsl:value-of select="substring-before($rcvLad, ':')"/>
				</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<xsl:variable name="cusEndpointValue">
			<xsl:choose>
				<xsl:when test="$cusPeppolID != ''">
					<xsl:value-of select="substring-after($cusPeppolID, ':')"/>
				</xsl:when>
				<xsl:otherwise>
					<xsl:value-of select="substring-after($rcvLad, ':')"/>
				</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>

		<!-- Totals from E1EDS01 -->
		<!-- SUMID 010: Net Amount -->
		<!-- SUMID 011: Gross Amount (Tax Inclusive) -->
		<!-- SUMID 005: Tax Amount -->
		<xsl:variable name="totalNet" select="INVOIC02/IDOC/E1EDS01[SUMID='010']/SUMME"/>
		<xsl:variable name="totalGross" select="INVOIC02/IDOC/E1EDS01[SUMID='011']/SUMME"/>
		<xsl:variable name="totalTax" select="INVOIC02/IDOC/E1EDS01[SUMID='005']/SUMME"/>

		<!-- Fallback if E1EDS01 is missing (using calculation) -->
		<xsl:variable name="calcLineNetTotal">
			<xsl:call-template name="sum-decimal">
				<xsl:with-param name="nodes" select="INVOIC02/IDOC/E1EDP01/E1EDP26[QUALF='003']/BETRG"/>
			</xsl:call-template>
		</xsl:variable>
		<xsl:variable name="calcTaxTotal">
			<xsl:call-template name="sum-decimal">
				<xsl:with-param name="nodes" select="INVOIC02/IDOC/E1EDP01/E1EDP04/MWSBT"/>
			</xsl:call-template>
		</xsl:variable>

		<!-- Final Variables for Totals -->
		<xsl:variable name="finalNet">
			<xsl:choose>
				<xsl:when test="$totalNet != ''"><xsl:value-of select="$totalNet"/></xsl:when>
				<xsl:otherwise><xsl:value-of select="$calcLineNetTotal"/></xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<xsl:variable name="finalTax">
			<xsl:choose>
				<xsl:when test="$totalTax != ''"><xsl:value-of select="$totalTax"/></xsl:when>
				<xsl:otherwise><xsl:value-of select="$calcTaxTotal"/></xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<xsl:variable name="finalGross">
			<xsl:choose>
				<xsl:when test="$totalGross != ''"><xsl:value-of select="$totalGross"/></xsl:when>
				<xsl:otherwise><xsl:value-of select="number($finalNet) + number($finalTax)"/></xsl:otherwise>
			</xsl:choose>
		</xsl:variable>

		<!-- ======================== DETECT CREDIT NOTE ======================== -->
		<xsl:variable name="isCreditNote">
			<xsl:choose>
				<xsl:when test="$k01/BSART = 'KG'">true</xsl:when>
				<xsl:otherwise>false</xsl:otherwise>
			</xsl:choose>
		</xsl:variable>
		<xsl:choose>
			<!-- **************************************************************** -->
			<!-- ************************ CREDIT NOTE *************************** -->
			<!-- **************************************************************** -->
			<xsl:when test="$isCreditNote = 'true'">
				<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
					<cbc:UBLVersionID>2.1</cbc:UBLVersionID>
					<cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0</cbc:CustomizationID>
					<cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>
					<cbc:ID>
						<xsl:value-of select="$k01/BELNR"/>
					</cbc:ID>
					<cbc:IssueDate>
						<xsl:choose>
							<xsl:when test="string-length($headerDateIssueRaw)=8">
								<xsl:value-of select="concat(substring($headerDateIssueRaw,1,4),'-',substring($headerDateIssueRaw,5,2),'-',substring($headerDateIssueRaw,7,2))"/>
							</xsl:when>
							<xsl:otherwise>1970-01-01</xsl:otherwise>
						</xsl:choose>
					</cbc:IssueDate>
					<xsl:if test="$headerDateDueRaw!=''">
						<cbc:DueDate>
							<xsl:choose>
								<xsl:when test="string-length($headerDateDueRaw)=8">
									<xsl:value-of select="concat(substring($headerDateDueRaw,1,4),'-',substring($headerDateDueRaw,5,2),'-',substring($headerDateDueRaw,7,2))"/>
								</xsl:when>
								<xsl:otherwise>1970-01-01</xsl:otherwise>
							</xsl:choose>
						</cbc:DueDate>
					</xsl:if>
					<cbc:CreditNoteTypeCode>381</cbc:CreditNoteTypeCode>
					<cbc:DocumentCurrencyCode>
						<xsl:value-of select="$currency"/>
					</cbc:DocumentCurrencyCode>

					<!-- Buyer Reference: Mandatory in Peppol -->
					<xsl:variable name="buyerRef" select="INVOIC02/IDOC/E1EDK02[QUALF='001'][1]/BELNR"/>
					<cbc:BuyerReference>
						<xsl:choose>
							<xsl:when test="$buyerRef != ''">
								<xsl:value-of select="$buyerRef"/>
							</xsl:when>
							<xsl:otherwise>
								<xsl:value-of select="$k01/RECIPNT_NO"/>
							</xsl:otherwise>
						</xsl:choose>
					</cbc:BuyerReference>

					<!-- Order reference -->
					<xsl:if test="INVOIC02/IDOC/E1EDK02[QUALF='002']">
						<cac:OrderReference>
							<cbc:ID>
								<xsl:value-of select="INVOIC02/IDOC/E1EDK02[QUALF='002'][1]/BELNR"/>
							</cbc:ID>
						</cac:OrderReference>
					</xsl:if>
					<!-- Supplier Party -->
					<cac:AccountingSupplierParty>
						<cac:Party>
							<cbc:EndpointID>
								<xsl:attribute name="schemeID"><xsl:choose><xsl:when test="$supEndpointScheme!=''"><xsl:value-of select="$supEndpointScheme"/></xsl:when><xsl:otherwise>0208</xsl:otherwise></xsl:choose></xsl:attribute>
								<xsl:value-of select="$supEndpointValue"/>
							</cbc:EndpointID>
							<cac:PartyName>
								<cbc:Name>
									<xsl:value-of select="$sup/NAME1"/>
								</cbc:Name>
							</cac:PartyName>
							<cac:PostalAddress>
								<cbc:StreetName>
									<xsl:value-of select="$sup/STRAS"/>
								</cbc:StreetName>
								<cbc:CityName>
									<xsl:value-of select="$sup/ORT01"/>
								</cbc:CityName>
								<cbc:PostalZone>
									<xsl:value-of select="$sup/PSTLZ"/>
								</cbc:PostalZone>
								<cac:Country>
									<cbc:IdentificationCode>
										<xsl:value-of select="$sup/LAND1"/>
									</cbc:IdentificationCode>
								</cac:Country>
							</cac:PostalAddress>
							<cac:PartyTaxScheme>
								<cbc:CompanyID>
									<xsl:value-of select="$supVatFull"/>
								</cbc:CompanyID>
								<cac:TaxScheme>
									<cbc:ID>VAT</cbc:ID>
								</cac:TaxScheme>
							</cac:PartyTaxScheme>
							<cac:PartyLegalEntity>
								<cbc:RegistrationName>
									<xsl:value-of select="$sup/NAME1"/>
								</cbc:RegistrationName>
								<cbc:CompanyID>
									<xsl:value-of select="$supVat"/>
								</cbc:CompanyID>
							</cac:PartyLegalEntity>
						</cac:Party>
					</cac:AccountingSupplierParty>
					<!-- Customer Party -->
					<cac:AccountingCustomerParty>
						<cac:Party>
							<cbc:EndpointID>
								<xsl:attribute name="schemeID"><xsl:choose><xsl:when test="$cusEndpointScheme!=''"><xsl:value-of select="$cusEndpointScheme"/></xsl:when><xsl:otherwise>0208</xsl:otherwise></xsl:choose></xsl:attribute>
								<xsl:value-of select="$cusEndpointValue"/>
							</cbc:EndpointID>
							<cac:PartyName>
								<cbc:Name>
									<xsl:value-of select="$cus/NAME1"/>
								</cbc:Name>
							</cac:PartyName>
							<cac:PostalAddress>
								<cbc:StreetName>
									<xsl:value-of select="$cus/STRAS"/>
								</cbc:StreetName>
								<cbc:CityName>
									<xsl:value-of select="$cus/ORT01"/>
								</cbc:CityName>
								<cbc:PostalZone>
									<xsl:value-of select="$cus/PSTLZ"/>
								</cbc:PostalZone>
								<cac:Country>
									<cbc:IdentificationCode>
										<xsl:value-of select="$cus/LAND1"/>
									</cbc:IdentificationCode>
								</cac:Country>
							</cac:PostalAddress>
							<cac:PartyLegalEntity>
								<cbc:RegistrationName>
									<xsl:value-of select="$cus/NAME1"/>
								</cbc:RegistrationName>
								<cbc:CompanyID>
									<xsl:value-of select="$cusVat"/>
								</cbc:CompanyID>
							</cac:PartyLegalEntity>
						</cac:Party>
					</cac:AccountingCustomerParty>
					<!-- Payment Means -->
					<cac:PaymentMeans>
						<cbc:PaymentMeansCode>30</cbc:PaymentMeansCode>
						<xsl:if test="INVOIC02/IDOC/E1EDK28">
							<xsl:variable name="bank" select="INVOIC02/IDOC/E1EDK28[1]"/>
							<cac:PayeeFinancialAccount>
								<cbc:ID>
									<xsl:value-of select="$bank/BIBAN"/>
								</cbc:ID>
								<cbc:Name>
									<xsl:value-of select="$bank/ACNAM"/>
								</cbc:Name>
							</cac:PayeeFinancialAccount>
						</xsl:if>
					</cac:PaymentMeans>
					<!-- Payment Terms -->
					<xsl:if test="INVOIC02/IDOC/E1EDK18">
						<cac:PaymentTerms>
							<cbc:Note>
								<xsl:value-of select="INVOIC02/IDOC/E1EDK18/ZTERM_TXT"/>
							</cbc:Note>
						</cac:PaymentTerms>
					</xsl:if>
					<!-- Tax Total -->
					<cac:TaxTotal>
						<cbc:TaxAmount currencyID="{$currency}">
							<xsl:value-of select="format-number(number($finalTax),'0.00')"/>
						</cbc:TaxAmount>
						<xsl:for-each select="INVOIC02/IDOC/E1EDP01/E1EDP04[generate-id()=generate-id(key('taxByRate',MSATZ)[1])]">
							<xsl:variable name="rate" select="MSATZ"/>
							<xsl:variable name="taxableAmount">
								<xsl:call-template name="sum-decimal">
									<xsl:with-param name="nodes" select="/INVOIC02/IDOC/E1EDP01[E1EDP04/MSATZ=$rate]/E1EDP26[QUALF='003']/BETRG"/>
								</xsl:call-template>
							</xsl:variable>
							<xsl:variable name="taxAmount">
								<xsl:call-template name="sum-decimal">
									<xsl:with-param name="nodes" select="/INVOIC02/IDOC/E1EDP01/E1EDP04[MSATZ=$rate]/MWSBT"/>
								</xsl:call-template>
							</xsl:variable>
							<cac:TaxSubtotal>
								<cbc:TaxableAmount currencyID="{$currency}">
									<xsl:value-of select="format-number(number($taxableAmount),'0.00')"/>
								</cbc:TaxableAmount>
								<cbc:TaxAmount currencyID="{$currency}">
									<xsl:value-of select="format-number(number($taxAmount),'0.00')"/>
								</cbc:TaxAmount>
								<cac:TaxCategory>
									<cbc:ID>S</cbc:ID>
									<cbc:Percent>
										<xsl:value-of select="$rate"/>
									</cbc:Percent>
									<cac:TaxScheme>
										<cbc:ID>VAT</cbc:ID>
									</cac:TaxScheme>
								</cac:TaxCategory>
							</cac:TaxSubtotal>
						</xsl:for-each>
					</cac:TaxTotal>
					<!-- Credit Note Monetary Total -->
					<cac:LegalMonetaryTotal>
						<cbc:LineExtensionAmount currencyID="{$currency}">
							<xsl:value-of select="format-number(number($finalNet),'0.00')"/>
						</cbc:LineExtensionAmount>
						<cbc:TaxExclusiveAmount currencyID="{$currency}">
							<xsl:value-of select="format-number(number($finalNet),'0.00')"/>
						</cbc:TaxExclusiveAmount>
						<cbc:TaxInclusiveAmount currencyID="{$currency}">
							<xsl:value-of select="format-number(number($finalGross),'0.00')"/>
						</cbc:TaxInclusiveAmount>
						<cbc:PayableAmount currencyID="{$currency}">
							<xsl:value-of select="format-number(number($finalGross),'0.00')"/>
						</cbc:PayableAmount>
					</cac:LegalMonetaryTotal>
					<!-- CreditNote Lines -->
					<xsl:for-each select="INVOIC02/IDOC/E1EDP01">
						<xsl:variable name="line" select="."/>
						<xsl:variable name="lineNet">
							<xsl:call-template name="sum-decimal">
								<xsl:with-param name="nodes" select="$line/E1EDP26[QUALF='003']/BETRG"/>
							</xsl:call-template>
						</xsl:variable>
						<xsl:variable name="linePriceRaw">
							<xsl:choose>
								<xsl:when test="$line/E1EDP05/KRATE!=''">
									<xsl:value-of select="translate($line/E1EDP05/KRATE,',','.')"/>
								</xsl:when>
								<xsl:otherwise>0</xsl:otherwise>
							</xsl:choose>
						</xsl:variable>
						<xsl:variable name="lineCurrency">
							<xsl:choose>
								<xsl:when test="$line/E1EDP05/KOEIN!=''">
									<xsl:value-of select="$line/E1EDP05/KOEIN"/>
								</xsl:when>
								<xsl:otherwise>
									<xsl:value-of select="$currency"/>
								</xsl:otherwise>
							</xsl:choose>
						</xsl:variable>
						<xsl:variable name="unitCode">
							<xsl:choose>
								<xsl:when test="$line/MENEE='PCE'">C62</xsl:when>
								<xsl:otherwise>
									<xsl:value-of select="$line/MENEE"/>
								</xsl:otherwise>
							</xsl:choose>
						</xsl:variable>
						<xsl:variable name="shortText" select="$line/E1EDP19[QUALF='002']/KTEXT"/>
						<xsl:variable name="lineVatRate" select="$line/E1EDP04/MSATZ"/>
						<cac:CreditNoteLine>
							<cbc:ID>
								<xsl:choose>
									<xsl:when test="string-length($line/POSEX)&gt;0">
										<xsl:value-of select="number($line/POSEX)"/>
									</xsl:when>
									<xsl:otherwise>1</xsl:otherwise>
								</xsl:choose>
							</cbc:ID>
							<cbc:CreditedQuantity unitCode="{$unitCode}">
								<xsl:value-of select="format-number(number($line/MENGE), '0.00')"/>
							</cbc:CreditedQuantity>
							<cbc:LineExtensionAmount currencyID="{$currency}">
								<xsl:value-of select="format-number(number($lineNet),'0.00')"/>
							</cbc:LineExtensionAmount>
							<cac:Item>
								<cbc:Description>
									<xsl:value-of select="$shortText"/>
								</cbc:Description>
								<cbc:Name>
									<xsl:value-of select="$shortText"/>
								</cbc:Name>
								<cac:ClassifiedTaxCategory>
									<cbc:ID>S</cbc:ID>
									<cbc:Percent>
										<xsl:value-of select="$lineVatRate"/>
									</cbc:Percent>
									<cac:TaxScheme>
										<cbc:ID>VAT</cbc:ID>
									</cac:TaxScheme>
								</cac:ClassifiedTaxCategory>
							</cac:Item>
							<cac:Price>
								<cbc:PriceAmount currencyID="{$lineCurrency}">
									<xsl:value-of select="format-number(number($linePriceRaw),'0.0000')"/>
								</cbc:PriceAmount>
								<cbc:BaseQuantity unitCode="{$unitCode}">1</cbc:BaseQuantity>
							</cac:Price>
						</cac:CreditNoteLine>
					</xsl:for-each>
				</CreditNote>
			</xsl:when>
			<!-- **************************************************************** -->
			<!-- *************************** INVOICE **************************** -->
			<!-- **************************************************************** -->
			<xsl:otherwise>
				<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2" xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
					<cbc:UBLVersionID>2.1</cbc:UBLVersionID>
					<cbc:CustomizationID>urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0</cbc:CustomizationID>
					<cbc:ProfileID>urn:fdc:peppol.eu:2017:poacc:billing:01:1.0</cbc:ProfileID>
					<cbc:ID>
						<xsl:value-of select="$k01/BELNR"/>
					</cbc:ID>
					<cbc:IssueDate>
						<xsl:choose>
							<xsl:when test="string-length($headerDateIssueRaw)=8">
								<xsl:value-of select="concat(substring($headerDateIssueRaw,1,4),'-',substring($headerDateIssueRaw,5,2),'-',substring($headerDateIssueRaw,7,2))"/>
							</xsl:when>
							<xsl:otherwise>1970-01-01</xsl:otherwise>
						</xsl:choose>
					</cbc:IssueDate>
					<xsl:if test="$headerDateDueRaw!=''">
						<cbc:DueDate>
							<xsl:choose>
								<xsl:when test="string-length($headerDateDueRaw)=8">
									<xsl:value-of select="concat(substring($headerDateDueRaw,1,4),'-',substring($headerDateDueRaw,5,2),'-',substring($headerDateDueRaw,7,2))"/>
								</xsl:when>
								<xsl:otherwise>1970-01-01</xsl:otherwise>
							</xsl:choose>
						</cbc:DueDate>
					</xsl:if>
					<cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
					<cbc:DocumentCurrencyCode>
						<xsl:value-of select="$currency"/>
					</cbc:DocumentCurrencyCode>

					<!-- Buyer Reference: Mandatory in Peppol -->
					<xsl:variable name="buyerRef" select="INVOIC02/IDOC/E1EDK02[QUALF='001'][1]/BELNR"/>
					<cbc:BuyerReference>
						<xsl:choose>
							<xsl:when test="$buyerRef != ''">
								<xsl:value-of select="$buyerRef"/>
							</xsl:when>
							<xsl:otherwise>
								<xsl:value-of select="$k01/RECIPNT_NO"/>
							</xsl:otherwise>
						</xsl:choose>
					</cbc:BuyerReference>

					<xsl:if test="INVOIC02/IDOC/E1EDK02[QUALF='002']">
						<cac:OrderReference>
							<cbc:ID>
								<xsl:value-of select="INVOIC02/IDOC/E1EDK02[QUALF='002'][1]/BELNR"/>
							</cbc:ID>
						</cac:OrderReference>
					</xsl:if>
					<!-- Supplier Party -->
					<cac:AccountingSupplierParty>
						<cac:Party>
							<cbc:EndpointID>
								<xsl:attribute name="schemeID"><xsl:choose><xsl:when test="$supEndpointScheme!=''"><xsl:value-of select="$supEndpointScheme"/></xsl:when><xsl:otherwise>0208</xsl:otherwise></xsl:choose></xsl:attribute>
								<xsl:value-of select="$supEndpointValue"/>
							</cbc:EndpointID>
							<cac:PartyName>
								<cbc:Name>
									<xsl:value-of select="$sup/NAME1"/>
								</cbc:Name>
							</cac:PartyName>
							<cac:PostalAddress>
								<cbc:StreetName>
									<xsl:value-of select="$sup/STRAS"/>
								</cbc:StreetName>
								<cbc:CityName>
									<xsl:value-of select="$sup/ORT01"/>
								</cbc:CityName>
								<cbc:PostalZone>
									<xsl:value-of select="$sup/PSTLZ"/>
								</cbc:PostalZone>
								<cac:Country>
									<cbc:IdentificationCode>
										<xsl:value-of select="$sup/LAND1"/>
									</cbc:IdentificationCode>
								</cac:Country>
							</cac:PostalAddress>
							<cac:PartyTaxScheme>
								<cbc:CompanyID>
									<xsl:value-of select="$supVatFull"/>
								</cbc:CompanyID>
								<cac:TaxScheme>
									<cbc:ID>VAT</cbc:ID>
								</cac:TaxScheme>
							</cac:PartyTaxScheme>
							<cac:PartyLegalEntity>
								<cbc:RegistrationName>
									<xsl:value-of select="$sup/NAME1"/>
								</cbc:RegistrationName>
								<cbc:CompanyID>
									<xsl:value-of select="$supVat"/>
								</cbc:CompanyID>
							</cac:PartyLegalEntity>
						</cac:Party>
					</cac:AccountingSupplierParty>
					<!-- Customer Party -->
					<cac:AccountingCustomerParty>
						<cac:Party>
							<cbc:EndpointID>
								<xsl:attribute name="schemeID"><xsl:choose><xsl:when test="$cusEndpointScheme!=''"><xsl:value-of select="$cusEndpointScheme"/></xsl:when><xsl:otherwise>0208</xsl:otherwise></xsl:choose></xsl:attribute>
								<xsl:value-of select="$cusEndpointValue"/>
							</cbc:EndpointID>
							<cac:PartyName>
								<cbc:Name>
									<xsl:value-of select="$cus/NAME1"/>
								</cbc:Name>
							</cac:PartyName>
							<cac:PostalAddress>
								<cbc:StreetName>
									<xsl:value-of select="$cus/STRAS"/>
								</cbc:StreetName>
								<cbc:CityName>
									<xsl:value-of select="$cus/ORT01"/>
								</cbc:CityName>
								<cbc:PostalZone>
									<xsl:value-of select="$cus/PSTLZ"/>
								</cbc:PostalZone>
								<cac:Country>
									<cbc:IdentificationCode>
										<xsl:value-of select="$cus/LAND1"/>
									</cbc:IdentificationCode>
								</cac:Country>
							</cac:PostalAddress>
							<cac:PartyLegalEntity>
								<cbc:RegistrationName>
									<xsl:value-of select="$cus/NAME1"/>
								</cbc:RegistrationName>
								<cbc:CompanyID>
									<xsl:value-of select="$cusVat"/>
								</cbc:CompanyID>
							</cac:PartyLegalEntity>
						</cac:Party>
					</cac:AccountingCustomerParty>
					<!-- Payment Means -->
					<cac:PaymentMeans>
						<cbc:PaymentMeansCode>30</cbc:PaymentMeansCode>
						<xsl:if test="INVOIC02/IDOC/E1EDK28">
							<xsl:variable name="bank" select="INVOIC02/IDOC/E1EDK28[1]"/>
							<cac:PayeeFinancialAccount>
								<cbc:ID>
									<xsl:value-of select="$bank/BIBAN"/>
								</cbc:ID>
								<cbc:Name>
									<xsl:value-of select="$bank/ACNAM"/>
								</cbc:Name>
							</cac:PayeeFinancialAccount>
						</xsl:if>
					</cac:PaymentMeans>
					<!-- Payment Terms -->
					<xsl:if test="INVOIC02/IDOC/E1EDK18">
						<cac:PaymentTerms>
							<cbc:Note>
								<xsl:value-of select="INVOIC02/IDOC/E1EDK18/ZTERM_TXT"/>
							</cbc:Note>
						</cac:PaymentTerms>
					</xsl:if>
					<!-- Tax Total -->
					<cac:TaxTotal>
						<cbc:TaxAmount currencyID="{$currency}">
							<xsl:value-of select="format-number(number($finalTax),'0.00')"/>
						</cbc:TaxAmount>
						<xsl:for-each select="INVOIC02/IDOC/E1EDP01/E1EDP04[generate-id()=generate-id(key('taxByRate',MSATZ)[1])]">
							<xsl:variable name="rate" select="MSATZ"/>
							<xsl:variable name="taxableAmount">
								<xsl:call-template name="sum-decimal">
									<xsl:with-param name="nodes" select="/INVOIC02/IDOC/E1EDP01[E1EDP04/MSATZ=$rate]/E1EDP26[QUALF='003']/BETRG"/>
								</xsl:call-template>
							</xsl:variable>
							<xsl:variable name="taxAmount">
								<xsl:call-template name="sum-decimal">
									<xsl:with-param name="nodes" select="/INVOIC02/IDOC/E1EDP01/E1EDP04[MSATZ=$rate]/MWSBT"/>
								</xsl:call-template>
							</xsl:variable>
							<cac:TaxSubtotal>
								<cbc:TaxableAmount currencyID="{$currency}">
									<xsl:value-of select="format-number(number($taxableAmount),'0.00')"/>
								</cbc:TaxableAmount>
								<cbc:TaxAmount currencyID="{$currency}">
									<xsl:value-of select="format-number(number($taxAmount),'0.00')"/>
								</cbc:TaxAmount>
								<cac:TaxCategory>
									<cbc:ID>S</cbc:ID>
									<cbc:Percent>
										<xsl:value-of select="$rate"/>
									</cbc:Percent>
									<cac:TaxScheme>
										<cbc:ID>VAT</cbc:ID>
									</cac:TaxScheme>
								</cac:TaxCategory>
							</cac:TaxSubtotal>
						</xsl:for-each>
					</cac:TaxTotal>
					<!-- Monetary Totals -->
					<cac:LegalMonetaryTotal>
						<cbc:LineExtensionAmount currencyID="{$currency}">
							<xsl:value-of select="format-number(number($finalNet),'0.00')"/>
						</cbc:LineExtensionAmount>
						<cbc:TaxExclusiveAmount currencyID="{$currency}">
							<xsl:value-of select="format-number(number($finalNet),'0.00')"/>
						</cbc:TaxExclusiveAmount>
						<cbc:TaxInclusiveAmount currencyID="{$currency}">
							<xsl:value-of select="format-number(number($finalGross),'0.00')"/>
						</cbc:TaxInclusiveAmount>
						<cbc:PayableAmount currencyID="{$currency}">
							<xsl:value-of select="format-number(number($finalGross),'0.00')"/>
						</cbc:PayableAmount>
					</cac:LegalMonetaryTotal>
					<!-- INVOICE LINES -->
					<xsl:for-each select="INVOIC02/IDOC/E1EDP01">
						<xsl:variable name="line" select="."/>
						<xsl:variable name="lineNet">
							<xsl:call-template name="sum-decimal">
								<xsl:with-param name="nodes" select="$line/E1EDP26[QUALF='003']/BETRG"/>
							</xsl:call-template>
						</xsl:variable>
						<xsl:variable name="linePriceRaw">
							<xsl:choose>
								<xsl:when test="$line/E1EDP05/KRATE!=''">
									<xsl:value-of select="translate($line/E1EDP05/KRATE,',','.')"/>
								</xsl:when>
								<xsl:otherwise>0</xsl:otherwise>
							</xsl:choose>
						</xsl:variable>
						<xsl:variable name="lineCurrency">
							<xsl:choose>
								<xsl:when test="$line/E1EDP05/KOEIN!=''">
									<xsl:value-of select="$line/E1EDP05/KOEIN"/>
								</xsl:when>
								<xsl:otherwise>
									<xsl:value-of select="$currency"/>
								</xsl:otherwise>
							</xsl:choose>
						</xsl:variable>
						<xsl:variable name="unitCode">
							<xsl:choose>
								<xsl:when test="$line/MENEE='PCE'">C62</xsl:when>
								<xsl:otherwise>
									<xsl:value-of select="$line/MENEE"/>
								</xsl:otherwise>
							</xsl:choose>
						</xsl:variable>
						<xsl:variable name="shortText" select="$line/E1EDP19[QUALF='002']/KTEXT"/>
						<xsl:variable name="lineVatRate" select="$line/E1EDP04/MSATZ"/>
						<cac:InvoiceLine>
							<cbc:ID>
								<xsl:choose>
									<xsl:when test="string-length($line/POSEX)&gt;0">
										<xsl:value-of select="number($line/POSEX)"/>
									</xsl:when>
									<xsl:otherwise>1</xsl:otherwise>
								</xsl:choose>
							</cbc:ID>
							<cbc:InvoicedQuantity unitCode="{$unitCode}">
								<xsl:value-of select="format-number(number($line/MENGE), '0.00')"/>
							</cbc:InvoicedQuantity>
							<cbc:LineExtensionAmount currencyID="{$currency}">
								<xsl:value-of select="format-number(number($lineNet),'0.00')"/>
							</cbc:LineExtensionAmount>
							<cac:Item>
								<cbc:Description>
									<xsl:value-of select="$shortText"/>
								</cbc:Description>
								<cbc:Name>
									<xsl:value-of select="$shortText"/>
								</cbc:Name>
								<cac:ClassifiedTaxCategory>
									<cbc:ID>S</cbc:ID>
									<cbc:Percent>
										<xsl:value-of select="$lineVatRate"/>
									</cbc:Percent>
									<cac:TaxScheme>
										<cbc:ID>VAT</cbc:ID>
									</cac:TaxScheme>
								</cac:ClassifiedTaxCategory>
							</cac:Item>
							<cac:Price>
								<cbc:PriceAmount currencyID="{$lineCurrency}">
									<xsl:value-of select="format-number(number($linePriceRaw),'0.0000')"/>
								</cbc:PriceAmount>
								<cbc:BaseQuantity unitCode="{$unitCode}">1</cbc:BaseQuantity>
							</cac:Price>
						</cac:InvoiceLine>
					</xsl:for-each>
				</Invoice>
			</xsl:otherwise>
		</xsl:choose>
	</xsl:template>
</xsl:stylesheet>
