# import os
# import json
# import re
# import requests
# import frappe
# from frappe import _
# from frappe.utils import get_url
# from typing import List, Dict, Tuple, Optional



# @frappe.whitelist()
# def send_whatsapp_message_customer(doc, method=None):
#     """
#     Triggered on After Insert / On Submit for Customer-related docs.
#     """
#     return _send_whatsapp_message(
#         doc=doc,
#         party_doctype="Customer",
#         project_field="project",
#     )


# @frappe.whitelist()
# def send_whatsapp_message_supplier(doc, method=None):
#     """
#     Triggered on After Insert / On Submit for Supplier-related docs.
#     """
#     return _send_whatsapp_message(
#         doc=doc,
#         party_doctype="Supplier",
#         project_field="custom_project",
#     )




# #  v-0.1 commented on 13 march 

# def _send_whatsapp_message(doc, party_doctype: str, project_field: str):
#     """
#     Common logic for sending WhatsApp message to Customer / Supplier + Employees.

#     Special cases:

#     - DPR:
#         * WhatsApp sirf tab trigger hoga jab:
#             - docstatus == 1  (Submitted)
#             - AND custom_dpr_status in:
#                 - "QC1(Structuring Done)"
#                 - "Packing And Dispatch"
#                 - "QC2(Surface Finishing)"

#     - WhatsApp Notification ErpNext:
#         * Agar custom_msg_to_only_employees == 1:
#             - Sirf Employees ko message jayega
#             - body_1 hamesha Employee.employee_name se fill hoga
#         * Else:
#             - Purana behaviour (employees + phone config) as-is.
#     """
#     try:
#         # 1. Template doc laao
#         template_doc = _get_whatsapp_template_for_doctype(doc.doctype)
#         if not template_doc:
#             msg = f"No WhatsApp notification found for {doc.doctype}"
#             frappe.log_error("WhatsApp Error", msg)
#             return {"status": "error", "message": msg}

#         # Flag: sirf employees ko bhejna?
#         only_employees = bool(template_doc.get("custom_msg_to_only_employees"))

#         # 2. Current doc reload
#         current_doc = frappe.get_doc(doc.doctype, doc.name)

#         # 2A. Docstatus check with DPR custom logic
#         if current_doc.doctype == "DPR":
#             allowed_statuses = [
#                 "QC1(Structuring Done)",
#                 "Packing And Dispatch",
#                 "QC2(Surface Finishing)",
#             ]
#             current_status = (current_doc.get("custom_dpr_status") or "").strip()

#             # DPR ke liye:
#             # - docstatus == 1 (Submitted) hona chahiye
#             # - AND status allowed list me hona chahiye
#             if current_doc.docstatus != 1 or current_status not in allowed_statuses:
#                 return {
#                     "status": "ignored",
#                     "message": "DPR not submitted or status not in allowed list.",
#                 }
#         else:
#             # Baaki sab doctypes: strict docstatus == 1
#             if current_doc.docstatus != 1:
#                 return {
#                     "status": "ignored",
#                     "message": "Docstatus is not submitted. (docstatus != 1)",
#                 }

#         # 2B. Dict bana lo further use ke liye
#         doc_dict = current_doc.as_dict()

#         # 3. Components + base template params + index map
#         (
#             components,
#             base_template_params,
#             text_key_index,
#         ) = _build_components_and_params(
#             template_doc=template_doc,
#             current_doc=current_doc,
#             doc_dict=doc_dict,
#             project_field=project_field,
#         )

#         campaignname = template_doc.get("campaignname") or ""

#         # Common: document component (agar hai)
#         document_component = next(
#             (v for v in components.values() if v["type"] == "document"),
#             None,
#         )

#         responses = []

#         # ------------------------------------------------------
#         # MODE 1: Sirf Employees ko message (personalised body_1)
#         # ------------------------------------------------------
#         if only_employees:
#             employees = frappe.get_all(
#                 "Employee",
#                 filters={"status": "Active", "custom_trigger_whatsapp_msg": 1},
#                 fields=["name", "employee_name", "cell_number"],
#             )

#             body1_idx = text_key_index.get("body_1")
#             all_numbers: List[str] = []

#             for emp in employees:
#                 if not emp.cell_number:
#                     continue

#                 number = _format_mobile(emp.cell_number)
#                 if not number:
#                     continue

#                 # Per-employee template params (copy)
#                 template_params = list(base_template_params)

#                 # body_1 hamesha employee_name se
#                 if body1_idx is not None:
#                     template_params[body1_idx] = emp.employee_name or emp.name

#                 payload = {
#                     "campaignName": campaignname,
#                     "destination": number,
#                     "userName": "Lakdi.com 6210",
#                     "source": "new-landing-page form",
#                     "templateParams": template_params,
#                     "tags": [doc.doctype],
#                     "attributes": {
#                         "docname": doc.name,
#                         "employee": emp.name,
#                     },
#                 }

#                 if document_component:
#                     payload["media"] = {
#                         "url": document_component["value"],
#                         "filename": document_component["filename"],
#                     }

#                 frappe.log_error(
#                     "Dynamic MSG91 Payload (Employees Only)",
#                     json.dumps({"number": number, "payload": payload}, indent=2),
#                 )

#                 api_response = send_whatsapp_api_call(payload)
#                 responses.append({"number": number, "response": api_response})
#                 all_numbers.append(number)

#             if not all_numbers:
#                 return {
#                     "status": "ignored",
#                     "message": "No employee mobile numbers found.",
#                 }

#             return {
#                 "status": "success",
#                 "sent_to": all_numbers,
#                 "responses": responses,
#             }

#         # ------------------------------------------------------
#         # MODE 2: Normal behaviour (employees + phone config)
#         # ------------------------------------------------------
#         all_receiver_numbers = _get_all_receiver_numbers(
#             current_doc=current_doc,
#             party_doctype=party_doctype,
#             template_doc=template_doc,
#         )

#         if not all_receiver_numbers:
#             return {
#                 "status": "ignored",
#                 "message": "No receiver mobile numbers found.",
#             }

#         for number in all_receiver_numbers:
#             payload = {
#                 "campaignName": campaignname,
#                 "destination": number,  # final mobile number
#                 "userName": "Lakdi.com 6210",
#                 "source": "new-landing-page form",
#                 "templateParams": base_template_params,
#                 "tags": [doc.doctype],
#                 "attributes": {"docname": doc.name},
#             }

#             if document_component:
#                 payload["media"] = {
#                     "url": document_component["value"],
#                     "filename": document_component["filename"],
#                 }

#             frappe.log_error(
#                 "Dynamic MSG91 Payload",
#                 json.dumps({"number": number, "payload": payload}, indent=2),
#             )

#             api_response = send_whatsapp_api_call(payload)
#             responses.append({"number": number, "response": api_response})

#         return {
#             "status": "success",
#             "sent_to": all_receiver_numbers,
#             "responses": responses,
#         }

#     except Exception:
#         frappe.log_error("WhatsApp Error", frappe.get_traceback())
#         return {"status": "error", "message": "Something went wrong!"}

# def _get_whatsapp_template_for_doctype(reference_doctype: str):
#     """
#     Get WhatsApp Notification template doc for given reference doctype.
#     DocType Event: "After Insert" / "After Submit"
#     """
#     notification = frappe.get_all(
#         "WhatsApp Notification ErpNext",
#         filters={
#             "reference_doctype": reference_doctype,
#             "disabled": 0,
#             "doctype_event": ["in", ["After Insert", "After Submit"]],
#         },
#         fields=["name"],
#         limit_page_length=1,
#     )

#     if not notification:
#         return None

#     template_name = notification[0].name
#     return frappe.get_doc("WhatsApp Notification ErpNext", template_name)


# def _get_all_receiver_numbers(current_doc, party_doctype: str, template_doc) -> List[str]:
#     numbers = set()

#     # ------------ 1. Employees ------------
#     employees = frappe.get_all(
#         "Employee",
#         filters={"status": "Active", "custom_trigger_whatsapp_msg": 1},
#         fields=["cell_number"],
#     )
#     for emp in employees:
#         if emp.cell_number:
#             formatted = _format_mobile(emp.cell_number)
#             if formatted:
#                 numbers.add(formatted)

#     # ------------ 2. Phone No config se ------------
#     phone_config_text = (template_doc.get("custom_phone_no") or "").strip()

#     if phone_config_text:
#         # Comma OR newline se split
#         tokens = re.split(r"[,\n]+", phone_config_text)
#         tokens = [t.strip() for t in tokens if t.strip()]

#         for token in tokens:
#             # Agar token pure digits (+ optional) hai -> direct number
#             if re.match(r"^(\+?\d+)$", token):
#                 formatted = _format_mobile(token)
#                 if formatted:
#                     numbers.add(formatted)
#                 continue

#             # Otherwise treat as fieldname from current_doc
#             fieldname = token
#             if hasattr(current_doc, fieldname):
#                 raw_val = current_doc.get(fieldname)
#                 if not raw_val:
#                     continue

#                 # comma / newline / slash se split
#                 parts = re.split(r"[,\n/]+", str(raw_val))
#                 for p in parts:
#                     p = p.strip()
#                     if not p:
#                         continue
#                     formatted = _format_mobile(p)
#                     if formatted:
#                         numbers.add(formatted)
#     return list(numbers)


# def _format_mobile(raw_number: str) -> Optional[str]:
#     """
#     Clean & format mobile number with '91' prefix if not provided.
#     """
#     if not raw_number:
#         return None

#     num = str(raw_number).strip()
#     num = re.sub(r"\s+", "", num)  # remove spaces

#     if num.startswith("0"):
#         num = num[1:]

#     # Already with country code or plus
#     if num.startswith("91") or num.startswith("+"):
#         return num

#     # Default India code
#     return "91" + num


# def _build_components_and_params(
#     template_doc,
#     current_doc,
#     doc_dict: Dict,
#     project_field: str,
# ) -> Tuple[Dict[str, Dict], List[str], Dict[str, int]]:
#     """
#     Template ke variables ke basis pe components + template_params banao.
#     Saath hi text variables ka index map bhi return karega
#     (jaise 'body_1' kis index pe hai templateParams list ke andar).
#     """
#     variables = template_doc.get("whatsapp_message_variables") or []
#     components: Dict[str, Dict] = {}
#     template_params: List[str] = []
#     text_key_index: Dict[str, int] = {}

#     for row in variables:
#         var_key = row.variable_key
#         key_lower = (var_key or "").lower()
#         var_type = (row.variable_type or "").lower()
#         value = ""

#         # 1. Document (PDF)
#         if var_type == "document":
#             file_data = frappe.attach_print(
#                 doctype=current_doc.doctype,
#                 name=current_doc.name,
#                 print_format=getattr(current_doc, "custom_print_format", None)
#                 or template_doc.print_format,
#                 print_letterhead=False,
#                 doc=current_doc,
#             )
#             filename = f"{current_doc.name}.pdf"
#             pdf_url = create_public_file(file_data, current_doc)

#             components[var_key] = {
#                 "type": "document",
#                 "filename": filename,
#                 "value": pdf_url,
#             }
#             continue

#         # 2. Image
#         if var_type == "image":
#             sample_path = template_doc.sample or ""
#             filename = os.path.basename(sample_path) if sample_path else "image.jpg"

#             components[var_key] = {
#                 "type": "image",
#                 "filename": filename,
#                 "value": f"{frappe.utils.get_url()}{sample_path}" if sample_path else "",
#             }
#             continue

#         # 3. Text variables
#         variable_value = (row.variable_value or "").lower()

#         if row.variable_value and variable_value not in ["order_id", "project"]:
#             # direct field from doc
#             value = doc_dict.get(row.variable_value) or ""

#         elif key_lower == "body_2":
#             # workflow_state or status
#             value = doc_dict.get("workflow_state") or doc_dict.get("status") or ""

#         elif variable_value in ["order_id", "project"]:
#             # Project related handling
#             project = doc_dict.get(project_field)
#             token = ""
#             project_name = ""

#             if project:
#                 project_doc = frappe.get_doc("Project", project)
#                 token = getattr(project_doc, "custom_custom_public_token", "") or ""
#                 project_name = project_doc.project_name or project_doc.name

#             if key_lower == "project":
#                 value = str(project_name or "")
#             else:
#                 # For order_id -> token
#                 value = str(token or "")

#         # Default fallback (text)
#         components[var_key] = {"type": "text", "value": value}

#         idx = len(template_params)
#         template_params.append(str(value) if value is not None else "")
#         text_key_index[key_lower] = idx

#     return components, template_params, text_key_index


# def send_whatsapp_api_call(payload_data: dict):
#     """
#     Send WhatsApp message via AiSensy API.
#     Hardcoded api_url & api_key (development / quick setup ke liye).
#     """

#     api_url = "https://backend.aisensy.com/campaign/t1/api/v2"
#     api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY3Mzg0ODM1YzAzMWE1MGJlY2NiNWMwMSIsIm5hbWUiOiJMYWtkaS5jb20gNjIxMCIsImFwcE5hbWUiOiJBaVNlbnN5IiwiY2xpZW50SWQiOiI2NzM4NDgzNWMwMzFhNTBiZWNjYjViZjIiLCJhY3RpdmVQbGFuIjoiQkFTSUNfTU9OVEhMWSIsImlhdCI6MTczMTc0MTc0OX0.qTnTeWPDckIzj6ySjTr0T7yQjvCKmoxxeIQTrKS1byQ"  # AiSensy dashboard se

#     # Ensure apiKey is included in payload
#     payload_data["apiKey"] = api_key

#     headers = {"Content-Type": "application/json"}

#     try:
#         # Request log
#         frappe.log_error(
#             "AiSensy Request",
#             json.dumps({"url": api_url, "payload": payload_data}, indent=2),
#         )

#         response = requests.post(api_url, headers=headers, json=payload_data)

#         # Response log
#         frappe.log_error(
#             "AiSensy Response",
#             json.dumps(
#                 {"status_code": response.status_code, "body": response.text},
#                 indent=2,
#             ),
#         )

#         response.raise_for_status()

#         return (
#             response.json()
#             if response.text
#             else {
#                 "status": "success",
#                 "message": "No Body",
#             }
#         )

#     except Exception as e:
#         frappe.log_error(
#             title="AiSensy WhatsApp API Call Failed",
#             message=json.dumps(
#                 {"error": str(e), "traceback": frappe.get_traceback()},
#                 indent=2,
#             ),
#         )
#         raise


# def create_public_file(file_data, doc):
#     """
#     Create a File document in Frappe, make it public, and return the public URL.
#     """
#     file_doc = frappe.get_doc(
#         {
#             "doctype": "File",
#             "file_name": file_data["fname"],
#             "content": file_data["fcontent"],
#             "is_private": 0,
#             "attached_to_doctype": doc.doctype,
#             "attached_to_name": doc.name,
#         }
#     )
#     file_doc.insert(ignore_permissions=True)
#     frappe.db.commit()

#     return get_url(file_doc.file_url)



















import os
import json
import re
import requests
import frappe
from frappe import _
from frappe.utils import get_url
from typing import List, Dict, Tuple, Optional


@frappe.whitelist()
def send_whatsapp_message_customer(doc, method=None):
    return _send_whatsapp_message(
        doc=doc,
        party_doctype="Customer",
        project_field="project",
    )


@frappe.whitelist()
def send_whatsapp_message_supplier(doc, method=None):
    return _send_whatsapp_message(
        doc=doc,
        party_doctype="Supplier",
        project_field="custom_project",
    )


# changed on 22 for Qc-2 additional trigger
# def _send_whatsapp_message(doc, party_doctype: str, project_field: str):
#     try:
#         template_doc = _get_whatsapp_template_for_doctype(doc.doctype)
#         if not template_doc:
#             msg = f"No WhatsApp notification found for {doc.doctype}"
#             frappe.log_error("WhatsApp Error", msg)
#             return {"status": "error", "message": msg}

#         only_employees = bool(template_doc.get("custom_msg_to_only_employees"))

#         current_doc = frappe.get_doc(doc.doctype, doc.name)

#         is_mrn_status = False

#         if current_doc.doctype == "DPR":
#             allowed_statuses = [
#                 "QC1(Structuring Done)",
#                 "Packing And Dispatch",
#                 "QC2(Surface Finishing)",
#                 "Installation",
#             ]
#             current_status = (current_doc.get("custom_dpr_status") or "").strip()

#             if current_doc.docstatus != 1:
#                 return {
#                     "status": "ignored",
#                     "message": "DPR not submitted.",
#                 }

#             if current_status == "MRN":
#                 is_mrn_status = True
#             elif current_status not in allowed_statuses:
#                 return {
#                     "status": "ignored",
#                     "message": "DPR status not in allowed list.",
#                 }
#         else:
#             if current_doc.docstatus != 1:
#                 return {
#                     "status": "ignored",
#                     "message": "Docstatus is not submitted. (docstatus != 1)",
#                 }

#         doc_dict = current_doc.as_dict()

#         (
#             components,
#             base_template_params,
#             text_key_index,
#         ) = _build_components_and_params(
#             template_doc=template_doc,
#             current_doc=current_doc,
#             doc_dict=doc_dict,
#             project_field=project_field,
#         )

#         campaignname = template_doc.get("campaignname") or ""

#         document_component = next(
#             (v for v in components.values() if v["type"] == "document"),
#             None,
#         )

#         responses = []

#         if only_employees:
#             employees = frappe.get_all(
#                 "Employee",
#                 filters={"status": "Active", "custom_trigger_whatsapp_msg": 1},
#                 fields=["name", "employee_name", "cell_number"],
#             )

#             body1_idx = text_key_index.get("body_1")
#             all_numbers: List[str] = []

#             for emp in employees:
#                 if not emp.cell_number:
#                     continue

#                 number = _format_mobile(emp.cell_number)
#                 if not number:
#                     continue

#                 template_params = list(base_template_params)

#                 if body1_idx is not None:
#                     template_params[body1_idx] = emp.employee_name or emp.name

#                 payload = {
#                     "campaignName": campaignname,
#                     "destination": number,
#                     "userName": "Lakdi.com 6210",
#                     "source": "new-landing-page form",
#                     "templateParams": template_params,
#                     "tags": [doc.doctype],
#                     "attributes": {
#                         "docname": doc.name,
#                         "employee": emp.name,
#                     },
#                 }

#                 if document_component:
#                     payload["media"] = {
#                         "url": document_component["value"],
#                         "filename": document_component["filename"],
#                     }

#                 frappe.log_error(
#                     "Dynamic MSG91 Payload (Employees Only)",
#                     json.dumps({"number": number, "payload": payload}, indent=2),
#                 )

#                 api_response = send_whatsapp_api_call(payload)
#                 responses.append({"number": number, "response": api_response})
#                 all_numbers.append(number)

#             if not all_numbers:
#                 return {
#                     "status": "ignored",
#                     "message": "No employee mobile numbers found.",
#                 }

#             return {
#                 "status": "success",
#                 "sent_to": all_numbers,
#                 "responses": responses,
#             }

#         if current_doc.doctype == "DPR" and is_mrn_status:
#             all_receiver_numbers = set()

#             sales_person_no = current_doc.get("custom_sales_person_contact_no")
#             ceo_no = current_doc.get("custom_ceo_now")

#             for raw_no in [sales_person_no, ceo_no]:
#                 formatted = _format_mobile(raw_no)
#                 if formatted:
#                     all_receiver_numbers.add(formatted)

#             all_receiver_numbers = list(all_receiver_numbers)
#         else:
#             all_receiver_numbers = _get_all_receiver_numbers(
#                 current_doc=current_doc,
#                 party_doctype=party_doctype,
#                 template_doc=template_doc,
#             )

#         if not all_receiver_numbers:
#             return {
#                 "status": "ignored",
#                 "message": "No receiver mobile numbers found.",
#             }

#         for number in all_receiver_numbers:
#             payload = {
#                 "campaignName": campaignname,
#                 "destination": number,
#                 "userName": "Lakdi.com 6210",
#                 "source": "new-landing-page form",
#                 "templateParams": base_template_params,
#                 "tags": [doc.doctype],
#                 "attributes": {"docname": doc.name},
#             }

#             if document_component:
#                 payload["media"] = {
#                     "url": document_component["value"],
#                     "filename": document_component["filename"],
#                 }

#             frappe.log_error(
#                 "Dynamic MSG91 Payload",
#                 json.dumps({"number": number, "payload": payload}, indent=2),
#             )

#             api_response = send_whatsapp_api_call(payload)
#             responses.append({"number": number, "response": api_response})

#         return {
#             "status": "success",
#             "sent_to": all_receiver_numbers,
#             "responses": responses,
#         }

#     except Exception:
#         frappe.log_error("WhatsApp Error", frappe.get_traceback())
#         return {"status": "error", "message": "Something went wrong!"}



def _send_whatsapp_message(doc, party_doctype: str, project_field: str):
    try:
        template_doc = _get_whatsapp_template_for_doctype(doc.doctype)
        if not template_doc:
            msg = f"No WhatsApp notification found for {doc.doctype}"
            frappe.log_error("WhatsApp Error", msg)
            return {"status": "error", "message": msg}

        only_employees = bool(template_doc.get("custom_msg_to_only_employees"))

        current_doc = frappe.get_doc(doc.doctype, doc.name)

        is_mrn_status = False
        force_body_2_value = None

        if current_doc.doctype == "DPR":
            allowed_statuses = [
                "QC1(Structuring Done)",
                "Packing And Dispatch",
                "QC2(Surface Finishing)",
                "Installation",
            ]
            current_status = (current_doc.get("custom_dpr_status") or "").strip()
            workflow_state = (current_doc.get("workflow_state") or "").strip()

            # Special case:
            # Trigger even when docstatus = 0
            # if DPR status is QC2(Surface Finishing)
            # and workflow state is Sent For Accounts Manager Review
            if (
                current_status == "QC2(Surface Finishing)"
                and workflow_state == "Sent For Accounts Manager Review"
            ):
                force_body_2_value = "Sent for Quality Check-2 (Surface Finishing)"

            else:
                if current_doc.docstatus != 1:
                    return {
                        "status": "ignored",
                        "message": "DPR not submitted.",
                    }

                if current_status == "MRN":
                    is_mrn_status = True
                elif current_status not in allowed_statuses:
                    return {
                        "status": "ignored",
                        "message": "DPR status not in allowed list.",
                    }
        else:
            if current_doc.docstatus != 1:
                return {
                    "status": "ignored",
                    "message": "Docstatus is not submitted. (docstatus != 1)",
                }

        doc_dict = current_doc.as_dict()

        (
            components,
            base_template_params,
            text_key_index,
        ) = _build_components_and_params(
            template_doc=template_doc,
            current_doc=current_doc,
            doc_dict=doc_dict,
            project_field=project_field,
        )

        # Override body_2 only for the special DPR case
        body2_idx = text_key_index.get("body_2")
        if force_body_2_value is not None and body2_idx is not None:
            base_template_params[body2_idx] = force_body_2_value

        campaignname = template_doc.get("campaignname") or ""

        document_component = next(
            (v for v in components.values() if v["type"] == "document"),
            None,
        )

        responses = []

        if only_employees:
            employees = frappe.get_all(
                "Employee",
                filters={"status": "Active", "custom_trigger_whatsapp_msg": 1},
                fields=["name", "employee_name", "cell_number"],
            )

            body1_idx = text_key_index.get("body_1")
            all_numbers: List[str] = []

            for emp in employees:
                if not emp.cell_number:
                    continue

                number = _format_mobile(emp.cell_number)
                if not number:
                    continue

                template_params = list(base_template_params)

                if body1_idx is not None:
                    template_params[body1_idx] = emp.employee_name or emp.name

                payload = {
                    "campaignName": campaignname,
                    "destination": number,
                    "userName": "Lakdi.com 6210",
                    "source": "new-landing-page form",
                    "templateParams": template_params,
                    "tags": [doc.doctype],
                    "attributes": {
                        "docname": doc.name,
                        "employee": emp.name,
                    },
                }

                if document_component:
                    payload["media"] = {
                        "url": document_component["value"],
                        "filename": document_component["filename"],
                    }

                frappe.log_error(
                    "Dynamic MSG91 Payload (Employees Only)",
                    json.dumps({"number": number, "payload": payload}, indent=2),
                )

                api_response = send_whatsapp_api_call(payload)
                responses.append({"number": number, "response": api_response})
                all_numbers.append(number)

            if not all_numbers:
                return {
                    "status": "ignored",
                    "message": "No employee mobile numbers found.",
                }

            return {
                "status": "success",
                "sent_to": all_numbers,
                "responses": responses,
            }

        if current_doc.doctype == "DPR" and is_mrn_status:
            all_receiver_numbers = set()

            sales_person_no = current_doc.get("custom_sales_person_contact_no")
            ceo_no = current_doc.get("custom_ceo_now")

            for raw_no in [sales_person_no, ceo_no]:
                formatted = _format_mobile(raw_no)
                if formatted:
                    all_receiver_numbers.add(formatted)

            all_receiver_numbers = list(all_receiver_numbers)
        else:
            all_receiver_numbers = _get_all_receiver_numbers(
                current_doc=current_doc,
                party_doctype=party_doctype,
                template_doc=template_doc,
            )

        if not all_receiver_numbers:
            return {
                "status": "ignored",
                "message": "No receiver mobile numbers found.",
            }

        for number in all_receiver_numbers:
            payload = {
                "campaignName": campaignname,
                "destination": number,
                "userName": "Lakdi.com 6210",
                "source": "new-landing-page form",
                "templateParams": base_template_params,
                "tags": [doc.doctype],
                "attributes": {"docname": doc.name},
            }

            if document_component:
                payload["media"] = {
                    "url": document_component["value"],
                    "filename": document_component["filename"],
                }

            frappe.log_error(
                "Dynamic MSG91 Payload",
                json.dumps({"number": number, "payload": payload}, indent=2),
            )

            api_response = send_whatsapp_api_call(payload)
            responses.append({"number": number, "response": api_response})

        return {
            "status": "success",
            "sent_to": all_receiver_numbers,
            "responses": responses,
        }

    except Exception:
        frappe.log_error("WhatsApp Error", frappe.get_traceback())
        return {"status": "error", "message": "Something went wrong!"}

def _get_whatsapp_template_for_doctype(reference_doctype: str):
    notification = frappe.get_all(
        "WhatsApp Notification ErpNext",
        filters={
            "reference_doctype": reference_doctype,
            "disabled": 0,
            "doctype_event": ["in", ["After Insert", "After Submit"]],
        },
        fields=["name"],
        limit_page_length=1,
    )

    if not notification:
        return None

    template_name = notification[0].name
    return frappe.get_doc("WhatsApp Notification ErpNext", template_name)


def _get_all_receiver_numbers(current_doc, party_doctype: str, template_doc) -> List[str]:
    numbers = set()

    employees = frappe.get_all(
        "Employee",
        filters={"status": "Active", "custom_trigger_whatsapp_msg": 1},
        fields=["cell_number"],
    )
    for emp in employees:
        if emp.cell_number:
            formatted = _format_mobile(emp.cell_number)
            if formatted:
                numbers.add(formatted)

    phone_config_text = (template_doc.get("custom_phone_no") or "").strip()

    if phone_config_text:
        tokens = re.split(r"[,\n]+", phone_config_text)
        tokens = [t.strip() for t in tokens if t.strip()]

        for token in tokens:
            if re.match(r"^(\+?\d+)$", token):
                formatted = _format_mobile(token)
                if formatted:
                    numbers.add(formatted)
                continue

            fieldname = token
            if hasattr(current_doc, fieldname):
                raw_val = current_doc.get(fieldname)
                if not raw_val:
                    continue

                parts = re.split(r"[,\n/]+", str(raw_val))
                for p in parts:
                    p = p.strip()
                    if not p:
                        continue
                    formatted = _format_mobile(p)
                    if formatted:
                        numbers.add(formatted)

    return list(numbers)


def _format_mobile(raw_number: str) -> Optional[str]:
    if not raw_number:
        return None

    num = str(raw_number).strip()
    num = re.sub(r"\s+", "", num)

    if num.startswith("0"):
        num = num[1:]

    if num.startswith("91") or num.startswith("+"):
        return num

    return "91" + num


def _build_components_and_params(
    template_doc,
    current_doc,
    doc_dict: Dict,
    project_field: str,
) -> Tuple[Dict[str, Dict], List[str], Dict[str, int]]:
    variables = template_doc.get("whatsapp_message_variables") or []
    components: Dict[str, Dict] = {}
    template_params: List[str] = []
    text_key_index: Dict[str, int] = {}

    for row in variables:
        var_key = row.variable_key
        key_lower = (var_key or "").lower()
        var_type = (row.variable_type or "").lower()
        value = ""

        if var_type == "document":
            file_data = frappe.attach_print(
                doctype=current_doc.doctype,
                name=current_doc.name,
                print_format=getattr(current_doc, "custom_print_format", None)
                or template_doc.print_format,
                print_letterhead=False,
                doc=current_doc,
            )
            filename = f"{current_doc.name}.pdf"
            pdf_url = create_public_file(file_data, current_doc)

            components[var_key] = {
                "type": "document",
                "filename": filename,
                "value": pdf_url,
            }
            continue

        if var_type == "image":
            sample_path = template_doc.sample or ""
            filename = os.path.basename(sample_path) if sample_path else "image.jpg"

            components[var_key] = {
                "type": "image",
                "filename": filename,
                "value": f"{frappe.utils.get_url()}{sample_path}" if sample_path else "",
            }
            continue

        variable_value = (row.variable_value or "").lower()

        if row.variable_value and variable_value not in ["order_id", "project"]:
            value = doc_dict.get(row.variable_value) or ""

        elif key_lower == "body_2":
            value = doc_dict.get("workflow_state") or doc_dict.get("status") or ""

        elif variable_value in ["order_id", "project"]:
            project = doc_dict.get(project_field)
            token = ""
            project_name = ""

            if project:
                project_doc = frappe.get_doc("Project", project)
                token = getattr(project_doc, "custom_custom_public_token", "") or ""
                project_name = project_doc.project_name or project_doc.name

            if key_lower == "project":
                value = str(project_name or "")
            else:
                value = str(token or "")

        components[var_key] = {"type": "text", "value": value}

        idx = len(template_params)
        template_params.append(str(value) if value is not None else "")
        text_key_index[key_lower] = idx

    return components, template_params, text_key_index


def send_whatsapp_api_call(payload_data: dict):
    api_url = "https://backend.aisensy.com/campaign/t1/api/v2"
    api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjY3Mzg0ODM1YzAzMWE1MGJlY2NiNWMwMSIsIm5hbWUiOiJMYWtkaS5jb20gNjIxMCIsImFwcE5hbWUiOiJBaVNlbnN5IiwiY2xpZW50SWQiOiI2NzM4NDgzNWMwMzFhNTBiZWNjYjViZjIiLCJhY3RpdmVQbGFuIjoiQkFTSUNfTU9OVEhMWSIsImlhdCI6MTczMTc0MTc0OX0.qTnTeWPDckIzj6ySjTr0T7yQjvCKmoxxeIQTrKS1byQ"

    payload_data["apiKey"] = api_key

    headers = {"Content-Type": "application/json"}

    try:
        frappe.log_error(
            "AiSensy Request",
            json.dumps({"url": api_url, "payload": payload_data}, indent=2),
        )

        response = requests.post(api_url, headers=headers, json=payload_data)

        frappe.log_error(
            "AiSensy Response",
            json.dumps(
                {"status_code": response.status_code, "body": response.text},
                indent=2,
            ),
        )

        response.raise_for_status()

        return (
            response.json()
            if response.text
            else {
                "status": "success",
                "message": "No Body",
            }
        )

    except Exception as e:
        frappe.log_error(
            title="AiSensy WhatsApp API Call Failed",
            message=json.dumps(
                {"error": str(e), "traceback": frappe.get_traceback()},
                indent=2,
            ),
        )
        raise


def create_public_file(file_data, doc):
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_data["fname"],
            "content": file_data["fcontent"],
            "is_private": 0,
            "attached_to_doctype": doc.doctype,
            "attached_to_name": doc.name,
        }
    )
    file_doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return get_url(file_doc.file_url)
