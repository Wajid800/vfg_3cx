"""Mapping between Employee I9 Verification fields and the real AcroForm field
names inside the official I-9 PDF (I-9 DCS.pdf), extracted from the template.

Used by the PDF-fill step (Step 2) to produce a completed I-9 for each employee.
Text (/Tx) fields map 1:1 below; checkboxes and the List A/B/C document rows are
handled in code because they depend on citizenship_status and document rows.
"""

# ERPNext fieldname  ->  I-9 PDF AcroForm field name  (simple text fields)
I9_TEXT_MAP = {
    "employee_last_name": "Last Name (Family Name)",
    "employee_first_name": "First Name Given Name",
    "employee_middle_initial": "Employee Middle Initial (if any)",
    "other_last_names_used": "Employee Other Last Names Used (if any)",
    "address_line1": "Address Street Number and Name",
    "apartment_number": "Apt Number (if any)",
    "city": "City or Town",
    "zip_code": "ZIP Code",
    "date_of_birth": "Date of Birth mmddyyyy",
    "ssn": "US Social Security Number",
    "personal_email": "Employees E-mail Address",
    "cell_number": "Telephone Number",
    # immigration
    "i94_admission_number": "Form I94 Admission Number",
    "work_authorized_until": "Exp Date mmddyyyy",
    "foreign_passport_number": "Foreign Passport Number and Country of IssuanceRow1",
    # employee signature block
    "employee_signature_date": "Today's Date mmddyyy",
    # section 2 - employer
    "first_day_of_employment": "FirstDayEmployed mmddyyyy",
    "employer_representative_name_title": "Last Name First Name and Title of Employer or Authorized Representative",
    "employer_signature_date": "S2 Todays Date mmddyyyy",
    "employer_business_name": "Employers Business or Org Name",
    "employer_business_address": "Employers Business or Org Address",
    "additional_information": "Additional Information",
}

# "State" is an AcroForm choice (/Ch) field, not free text.
I9_STATE_FIELD = "State"

# Signature (/Tx) fields — filled with the typed signer name (image lives in ERP).
I9_EMPLOYEE_SIGNATURE_FIELD = "Signature of Employee"
I9_EMPLOYER_SIGNATURE_FIELD = "Signature of Employer or AR"

# Citizenship checkboxes (only one is ticked). "on" value discovered at fill time.
I9_CITIZENSHIP_CHECKBOX = {
    "A citizen of the United States": "CB_1",
    "A noncitizen national of the United States": "CB_2",
    "A lawful permanent resident": "CB_3",
    "An alien authorized to work": "CB_4",
}

# USCIS A-Number appears twice: one under "lawful permanent resident", one under
# "alien authorized to work". Pick per citizenship_status.
I9_USCIS_A_NUMBER_LPR = "3 A lawful permanent resident Enter USCIS or ANumber"
I9_USCIS_A_NUMBER_ALIEN = "USCIS ANumber"

# Alternative DHS procedure checkbox (Section 2)
I9_ALT_PROCEDURE_CHECKBOX = "CB_Alt"

# Document verification fields, keyed by (list, order).
# List A allows up to 3 documents; List B and List C one each.
I9_DOCUMENT_FIELDS = {
    ("List A", 1): {
        "title": "Document Title 1",
        "authority": "Issuing Authority 1",
        "number": "Document Number 0 (if any)",
        "expiration": "Expiration Date if any",
    },
    ("List A", 2): {
        "title": "Document Title 2 If any",
        "authority": "Issuing Authority_2",
        "number": "Document Number If any_2",
    },
    ("List A", 3): {
        "number": "Document Number if any_3",
    },
    ("List B", 1): {
        "title": "List B Document 1 Title",
        "authority": "List B Issuing Authority 1",
        "number": "List B Document Number 1",
        "expiration": "List B Expiration Date 1",
    },
    ("List C", 1): {
        "title": "List C Document Title 1",
        "authority": "List C Issuing Authority 1",
        "number": "List C Document Number 1",
        "expiration": "List C Expiration Date 1",
    },
}
