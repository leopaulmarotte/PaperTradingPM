import streamlit as st

def render_html_table(
    df,
    height=300,
    header_color="#1f2937",
    row_hover_color="#374151",
    text_color="#e5e7eb",
):
    html = f"""
    <style>
        .custom-table-wrapper {{
            max-height: {height}px;
            overflow-y: auto;
            border-radius: 8px;
            border: 1px solid #374151;
        }}

        table.custom-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            color: {text_color};
        }}

        table.custom-table thead {{
            position: sticky;
            top: 0;
            background-color: {header_color};
        }}

        table.custom-table th, table.custom-table td {{
            padding: 8px 10px;
            text-align: right;
        }}

        table.custom-table tbody tr:hover {{
            background-color: {row_hover_color};
        }}
    </style>

    <div class="custom-table-wrapper">
        <table class="custom-table">
            <thead>
                <tr>
                    {''.join(f"<th>{col}</th>" for col in df.columns)}
                </tr>
            </thead>
            <tbody>
                {''.join(
                    "<tr>" +
                    ''.join(f"<td>{val}</td>" for val in row) +
                    "</tr>"
                    for row in df.values
                )}
            </tbody>
        </table>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)
