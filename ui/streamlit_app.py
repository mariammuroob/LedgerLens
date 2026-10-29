
import requests
import streamlit as st
import pandas as pd

import os

API_URL = st.secrets.get(
    "LEDGERLENS_API_URL",
    os.getenv("LEDGERLENS_API_URL", "http://127.0.0.1:8000"),
)
st.set_page_config(
    page_title="LedgerLens",
    page_icon="📄",
    layout="wide",
)

st.title("LedgerLens")
st.caption("AI-assisted invoice processing | Human-reviewed decisions")

# Sidebar
st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "Choose a page",
    ["Dashboard", "Upload invoice", "Review invoices"],
)

def api_get(path):
    response = requests.get(f"{API_URL}{path}", timeout=30)
    response.raise_for_status()
    return response.json()

def api_post(path, payload=None, files=None):
    response = requests.post(
        f"{API_URL}{path}",
        json=payload,
        files=files,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()

def show_api_error(error):
    if isinstance(error, requests.HTTPError) and error.response is not None:
        try:
            detail = error.response.json().get("detail", error.response.text)
        except ValueError:
            detail = error.response.text
        st.error(f"API error: {detail}")
    else:
        st.error(
            "Could not connect to the LedgerLens API. "
            "Make sure the API server is running."
        )

if page == "Dashboard":
    st.header("Invoice overview")

    try:
        invoices = api_get("/invoices")

        if invoices:
            df = pd.DataFrame(invoices)

            total = len(df)
            approved = int((df["status"] == "approved").sum())
            pending = int(
                df["status"].isin(
                    ["pending_review", "pending_classification"]
                ).sum()
            )
            rejected = int((df["status"] == "rejected").sum())

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total invoices", total)
            col2.metric("Approved", approved)
            col3.metric("Pending review", pending)
            col4.metric("Rejected", rejected)

            st.subheader("Recent invoices")
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.subheader("Invoice statuses")
            st.bar_chart(df["status"].value_counts())
        else:
            st.info("No invoices yet. Upload a PDF to get started.")

    except requests.RequestException as error:
        show_api_error(error)

elif page == "Upload invoice":
    st.header("Upload an invoice")
    st.write(
        "Upload an English digital PDF. LedgerLens extracts fields, "
        "runs validation checks, and suggests a category for human review."
    )

    uploaded_file = st.file_uploader(
        "Choose an invoice PDF",
        type=["pdf"],
    )

    if uploaded_file and st.button("Process invoice", type="primary"):
        try:
            with st.spinner("Extracting and validating invoice..."):
                result = api_post(
                    "/invoices",
                    files={
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            "application/pdf",
                        )
                    },
                )

            st.success(f"Invoice processed. ID: {result['invoice_id']}")
            st.write("**Status:**", result["status"])

            st.subheader("Extracted fields")
            st.json(result["extracted"])

            st.subheader("Validation")
            validation = result["validation"]
            if validation.get("valid"):
                st.success("All current validation checks passed.")
            else:
                st.warning("This invoice needs review.")
                st.write(validation.get("errors", []))

            st.subheader("Suggested category")
            classification = result.get("classification")
            if classification:
                st.write("**Category:**", classification["category"])
                st.write(
                    "**Model confidence:**",
                    f"{classification['confidence']:.1%}",
                )
            else:
                st.info("No category prediction was available.")

            st.info("Human review is still required.")

        except requests.RequestException as error:
            show_api_error(error)

elif page == "Review invoices":
    st.header("Human review")
    st.write(
        "Inspect an invoice before approving or rejecting it. "
        "Approval is blocked when the current validation checks fail."
    )

    try:
        invoices = api_get("/invoices")

        if not invoices:
            st.info("No invoices are available to review.")
        else:
            pending = [
                invoice for invoice in invoices
                if invoice["status"] in (
                    "pending_review",
                    "pending_classification",
                )
            ]

            if not pending:
                st.success("There are no pending invoices.")
            else:
                options = {
                    f"#{item['id']} — {item['filename']} "
                    f"({item['status']})": item["id"]
                    for item in pending
                }

                selected_label = st.selectbox(
                    "Select an invoice",
                    list(options.keys()),
                )
                invoice_id = options[selected_label]

                invoice = api_get(f"/invoices/{invoice_id}")

                st.subheader(f"Invoice #{invoice_id}")
                col1, col2 = st.columns(2)

                with col1:
                    st.write("**Vendor:**", invoice.get("vendor") or "—")
                    st.write(
                        "**Invoice number:**",
                        invoice.get("invoice_number") or "—",
                    )
                    st.write("**Date:**", invoice.get("date") or "—")
                    st.write("**Currency:**", invoice.get("currency") or "—")

                with col2:
                    st.write("**Subtotal:**", invoice.get("subtotal"))
                    st.write("**VAT:**", invoice.get("vat"))
                    st.write("**Total:**", invoice.get("total"))
                    st.write("**Valid:**", invoice.get("is_valid"))

                st.write(
                    "**Suggested category:**",
                    invoice.get("category") or "Unclassified",
                )
                confidence = invoice.get("category_confidence")
                if confidence is not None:
                    st.write(f"**Model confidence:** {confidence:.1%}")

                errors = invoice.get("validation_errors") or []
                if errors:
                    st.warning("Validation issues")
                    st.write(errors)
                else:
                    st.success("No validation errors recorded.")

                with st.expander("Review history"):
                    st.json(invoice.get("reviews", []))

                st.divider()
                st.subheader("Record your decision")

                category = st.text_input(
                    "Category",
                    value=invoice.get("category") or "",
                )
                reviewer = st.text_input("Reviewer", value="human")
                notes = st.text_area("Review notes")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button("Approve invoice", type="primary"):
                        try:
                            payload = {
                                "action": "approve",
                                "category": category or None,
                                "reviewer": reviewer or "human",
                                "notes": notes or None,
                            }
                            result = api_post(
                                f"/invoices/{invoice_id}/review",
                                payload=payload,
                            )
                            st.success(
                                f"Invoice #{invoice_id} approved."
                            )
                            st.json(result)
                            st.rerun()
                        except requests.RequestException as error:
                            show_api_error(error)

                with col2:
                    if st.button("Reject invoice"):
                        try:
                            payload = {
                                "action": "reject",
                                "category": category or None,
                                "reviewer": reviewer or "human",
                                "notes": notes or None,
                            }
                            result = api_post(
                                f"/invoices/{invoice_id}/review",
                                payload=payload,
                            )
                            st.success(
                                f"Invoice #{invoice_id} rejected."
                            )
                            st.json(result)
                            st.rerun()
                        except requests.RequestException as error:
                            show_api_error(error)

    except requests.RequestException as error:
        show_api_error(error)
