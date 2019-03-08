from flask_weasyprint import HTML


def create_pdf(pdf_data):
    return HTML('/templates/papertip.html'.format(pdf_data)).write_pdf()
