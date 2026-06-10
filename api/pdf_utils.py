import io
import base64
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.graphics.shapes import Drawing, Rect, Line, String

def generate_booking_pdf(booking):
    """
    Generates a premium, cinema-style PDF ticket using ReportLab.
    Returns the PDF bytes.
    """
    buffer = io.BytesIO()
    
    # Page setup - ticket size (standard letter but margins optimized)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    # Cyberpunk / Premium dark color palette
    c_primary = colors.HexColor("#06070d")   # Deep background
    c_secondary = colors.HexColor("#0d0f1e") # Card body background
    c_cyan = colors.HexColor("#00f2fe")      # Cyan accent
    c_magenta = colors.HexColor("#ff007f")   # Magenta accent
    c_text_muted = colors.HexColor("#8e9bb3")# Muted text
    c_border = colors.HexColor("#1b1e36")    # Thin border
    
    # Custom Paragraph Styles
    style_title_top = ParagraphStyle(
        'TitleTop',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=c_cyan,
        leading=12,
        spaceAfter=4
    )
    
    style_movie_title = ParagraphStyle(
        'MovieTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=colors.white,
        leading=28,
        spaceAfter=6
    )
    
    style_language = ParagraphStyle(
        'Language',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=c_magenta,
        leading=14,
        spaceAfter=15
    )
    
    style_booking_header = ParagraphStyle(
        'BookingHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=c_text_muted,
        leading=10,
        spaceAfter=2
    )
    
    style_booking_val = ParagraphStyle(
        'BookingVal',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        textColor=colors.white,
        leading=16
    )
    
    style_booking_cyan = ParagraphStyle(
        'BookingCyan',
        parent=style_booking_val,
        textColor=c_cyan
    )
    
    style_booking_green = ParagraphStyle(
        'BookingGreen',
        parent=style_booking_val,
        textColor=colors.HexColor("#00ff66")
    )
    
    style_id_label = ParagraphStyle(
        'IdLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=c_text_muted,
        leading=11,
        alignment=2 # Right align
    )
    
    style_id_val = ParagraphStyle(
        'IdVal',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        textColor=colors.white,
        leading=18,
        alignment=2 # Right align
    )

    story = []
    
    # 1. Main Header: "BROADCAST SECURED" Title Banner
    style_banner = ParagraphStyle(
        'Banner',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=c_cyan,
        leading=16,
        alignment=1, # Center
        spaceAfter=15
    )
    story.append(Paragraph("SHOWZY OFFICIAL BROADCAST SECURED", style_banner))
    story.append(Spacer(1, 10))
    
    # 2. Ticket Card Table Layout
    show = booking.show
    
    # Movie/Cinema Left Details
    details_left = [
        [
            Paragraph("OFFICIAL BROADCAST TICKET", style_title_top),
            Paragraph(f"BOOKING ID", style_id_label)
        ],
        [
            Paragraph(show.movie.title, style_movie_title),
            Paragraph(f"#SZ-{booking.id}", style_id_val)
        ],
        [
            Paragraph(f"{show.movie.language} &bull; {show.cinema.name}", style_language),
            ""
        ]
    ]
    
    details_table = Table(details_left, colWidths=[350, 150])
    details_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('SPAN', (0,2), (1,2)),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    
    # 3. Grid details & QR code row
    seats_list = [f"{ss.seat.row}{ss.seat.number}" for ss in booking.show_seats.all()]
    seats_str = ", ".join(seats_list)
    
    grid_data = [
        [
            Paragraph("DATE", style_booking_header),
            Paragraph("SHOWTIME", style_booking_header),
            ""
        ],
        [
            Paragraph(show.date.strftime('%a, %b %d, %Y'), style_booking_val),
            Paragraph(show.start_time.strftime('%H:%M'), style_booking_val),
            ""
        ],
        [
            Paragraph("SCREEN", style_booking_header),
            Paragraph("SEAT MATRIX", style_booking_header),
            ""
        ],
        [
            Paragraph(show.screen.name, style_booking_val),
            Paragraph(seats_str, style_booking_cyan),
            ""
        ],
        [
            Paragraph("PAYMENT", style_booking_header),
            Paragraph("STATUS", style_booking_header),
            ""
        ],
        [
            Paragraph(f"INR {float(booking.total_amount):.2f}", style_booking_val),
            Paragraph(booking.booking_status, style_booking_green),
            ""
        ]
    ]
    
    # Embed QR Code
    qr_img = None
    if booking.qr_image and booking.qr_image.startswith("data:image/png;base64,"):
        try:
            base64_data = booking.qr_image.split(",")[1]
            image_bytes = base64.b64decode(base64_data)
            image_io = io.BytesIO(image_bytes)
            qr_img = Image(ImageReader(image_io), width=120, height=120)
        except Exception:
            pass
            
    # Assemble the left details grid + QR code on the right
    # Row spans will place the QR code on the right side spanning 6 rows
    grid_rows = []
    for i in range(6):
        left_cols = [grid_data[i][0], grid_data[i][1]]
        if i == 0:
            grid_rows.append(left_cols + [qr_img or ""])
        else:
            grid_rows.append(left_cols + [""])
            
    grid_table = Table(grid_rows, colWidths=[180, 180, 140])
    grid_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('SPAN', (2,0), (2,5)), # Span QR Code across all rows
        ('ALIGN', (2,0), (2,5), 'CENTER'),
        ('VALIGN', (2,0), (2,5), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    
    # 4. Barcode Drawing
    barcode_drawing = Drawing(500, 30)
    barcode_drawing.add(Rect(0, 0, 500, 30, fillColor=c_secondary, strokeColor=colors.transparent))
    # Draw simple thin lines to resemble a barcode
    import random
    random.seed(booking.id)
    curr_x = 10
    while curr_x < 490:
        bar_w = random.choice([1, 2, 3])
        gap = random.choice([2, 4, 6])
        barcode_drawing.add(Rect(curr_x, 2, bar_w, 26, fillColor=colors.white, strokeColor=colors.transparent))
        curr_x += bar_w + gap
        
    barcode_label = Paragraph("TRANSACTION_VERIFIED_SECURE", ParagraphStyle(
        'BarcodeLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=c_text_muted,
        alignment=1,
        spaceBefore=5
    ))
    
    # 5. Combine everything inside a main card table to give a solid border/background
    card_content = [
        details_table,
        Spacer(1, 10),
        Table([[""]], colWidths=[500], rowHeights=[1], style=TableStyle([
            ('LINEBELOW', (0,0), (-1,-1), 1, c_border),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ])),
        Spacer(1, 15),
        grid_table,
        Spacer(1, 15),
        barcode_drawing,
        barcode_label
    ]
    
    # Main Ticket Border Container
    main_ticket_table = Table([[card_content]], colWidths=[520])
    main_ticket_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_secondary),
        ('BOX', (0,0), (-1,-1), 2, c_cyan),
        ('TOPPADDING', (0,0), (-1,-1), 20),
        ('BOTTOMPADDING', (0,0), (-1,-1), 20),
        ('LEFTPADDING', (0,0), (-1,-1), 20),
        ('RIGHTPADDING', (0,0), (-1,-1), 20),
    ]))
    
    story.append(main_ticket_table)
    
    # Build Document
    doc.build(story)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
