"""Mapping between Employee W4 fields and the AcroForm field names inside the
official W-4 PDF (fw4.pdf / pdf_templates/w4.pdf). The W-4 uses hierarchical
(XFA-style) field names, extracted from the template.
"""

_P = "topmostSubform[0].Page1[0]."

# ERPNext fieldname -> W-4 PDF text field (Page 1)
W4_TEXT_MAP = {
    "first_name_mi": _P + "Step1a[0].f1_01[0]",
    "last_name": _P + "Step1a[0].f1_02[0]",
    "address": _P + "Step1a[0].f1_03[0]",
    "city_state_zip": _P + "Step1a[0].f1_04[0]",
    "ssn": _P + "f1_05[0]",
    # Step 3
    "step3_qualifying_children": _P + "Step3_ReadOrder[0].f1_06[0]",
    "step3_other_dependents": _P + "Step3_ReadOrder[0].f1_07[0]",
    "step3_total": _P + "f1_08[0]",
    # Step 4
    "step4a_other_income": _P + "f1_09[0]",
    "step4b_deductions": _P + "f1_10[0]",
    "step4c_extra_withholding": _P + "f1_11[0]",
    # Employers Only (bottom of page 1)
    "employer_name_address": _P + "f1_12[0]",
    "employer_ein": _P + "f1_14[0]",
}

# Date field (Employers Only - First date of employment)
W4_FIRST_DATE_FIELD = _P + "f1_13[0]"

# Filing status is a radio group: each option is a separate widget with its own
# on-state. We set the selected one and force the others off.
W4_FILING_STATUS = {
    "Single or Married filing separately": (_P + "c1_1[0]", "/1"),
    "Married filing jointly or Qualifying surviving spouse": (_P + "c1_1[1]", "/2"),
    "Head of household": (_P + "c1_1[2]", "/3"),
}
W4_FILING_WIDGETS = [_P + "c1_1[0]", _P + "c1_1[1]", _P + "c1_1[2]"]

# Step 2(c) - multiple jobs checkbox
W4_MULTIPLE_JOBS_FIELD = _P + "c1_2[0]"
W4_MULTIPLE_JOBS_ON = "/1"
