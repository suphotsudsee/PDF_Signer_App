import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import io
import os
import sys
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- Config & Resource Path ---
def resource_path(relative_path):
    """ หา path ไฟล์สำหรับ EXE """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

FONT_FILE = resource_path('THSarabunNew.ttf') 
FONT_NAME = 'THSarabunNew'

class DocumentSignerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("โปรแกรมลงนามเอกสาร (PDF & Images)")
        self.root.geometry("1100x800")

        # ตัวแปรระบบ
        self.input_path = None
        self.input_type = None  # 'pdf' or 'image'
        self.sign_img_path = None
        self.processed_sign_img = None
        
        # ตัวแปรแสดงผล Preview
        self.preview_scale = 1.0
        self.tk_bg_image = None   # เก็บ reference ภาพพื้นหลัง
        self.tk_sign_image = None # เก็บ reference ภาพลายเซ็น
        self.real_img_size = (0, 0) # (width, height) ของไฟล์ต้นฉบับ

        self.setup_ui()

    def setup_ui(self):
        # --- Panel ซ้าย (Control) ---
        control_frame = tk.Frame(self.root, padx=15, pady=15, bg="#f0f0f0", width=320)
        control_frame.pack(side=tk.LEFT, fill=tk.Y)
        control_frame.pack_propagate(False)

        # 1. เลือกเอกสาร
        tk.Label(control_frame, text="1. เลือกไฟล์เอกสาร (PDF/JPG/PNG)", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Button(control_frame, text="📂 เปิดไฟล์เอกสาร", command=self.browse_input).pack(fill=tk.X, pady=5)
        self.lbl_input = tk.Label(control_frame, text="-", fg="gray", bg="#f0f0f0", wraplength=300, justify="left")
        self.lbl_input.pack(anchor="w", pady=(0, 15))

        # 2. เลือกลายเซ็น
        tk.Label(control_frame, text="2. เลือกลายเซ็น (ภาพ)", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Button(control_frame, text="🖊️ เปิดรูปลายเซ็น", command=self.browse_sign).pack(fill=tk.X, pady=5)
        self.lbl_sign = tk.Label(control_frame, text="-", fg="gray", bg="#f0f0f0", wraplength=300, justify="left")
        self.lbl_sign.pack(anchor="w", pady=(0, 15))

        # 3. วันที่
        tk.Label(control_frame, text="3. วันที่กำกับ", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(anchor="w")
        self.entry_date = tk.Entry(control_frame, font=("Arial", 12))
        self.entry_date.insert(0, "26 ธันวาคม 2568")
        self.entry_date.pack(fill=tk.X, pady=5)
        self.entry_date.bind("<KeyRelease>", self.update_preview_text)

        # ปุ่มบันทึก
        tk.Label(control_frame, text="----------------------", bg="#f0f0f0").pack(pady=10)
        self.btn_save = tk.Button(control_frame, text="💾 บันทึกไฟล์ใหม่", command=self.process_save, 
                                  bg="#007bff", fg="white", font=("Arial", 12, "bold"), state="disabled")
        self.btn_save.pack(side=tk.BOTTOM, fill=tk.X, pady=20)
        
        tk.Label(control_frame, text="วิธีใช้: ลากลายเซ็นไปวางบนภาพ\n(รองรับไฟล์รูปภาพและ PDF)", bg="#f0f0f0", fg="#d9534f").pack(side=tk.BOTTOM)

        # --- Panel ขวา (Canvas Preview) ---
        preview_frame = tk.Frame(self.root, bg="#333333")
        preview_frame.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH)
        
        # Scrollbars (เผื่อรูปใหญ่)
        self.v_scroll = tk.Scrollbar(preview_frame, orient=tk.VERTICAL)
        self.h_scroll = tk.Scrollbar(preview_frame, orient=tk.HORIZONTAL)
        
        self.canvas = tk.Canvas(preview_frame, bg="#555555", 
                                xscrollcommand=self.h_scroll.set, 
                                yscrollcommand=self.v_scroll.set,
                                cursor="hand2")
        
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)
        
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        # Dragging Logic
        self.drag_data = {"x": 0, "y": 0}
        self.canvas.bind("<Button-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)

    # --- Core Logic ---

    def make_transparent(self, img_path):
        """ ลบพื้นหลังสีขาวออกจากรูปลายเซ็น """
        img = Image.open(img_path).convert("RGBA")
        datas = img.getdata()
        new_data = []
        for item in datas:
            if item[0] > 200 and item[1] > 200 and item[2] > 200: # ขาวจั๊วะ
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        img.putdata(new_data)
        return img

    def browse_input(self):
        f = filedialog.askopenfilename(filetypes=[("Documents", "*.pdf;*.jpg;*.jpeg;*.png")])
        if f:
            self.input_path = f
            self.lbl_input.config(text=os.path.basename(f), fg="black")
            
            ext = os.path.splitext(f)[1].lower()
            if ext == '.pdf':
                self.input_type = 'pdf'
            else:
                self.input_type = 'image'
                
            self.load_preview_background()
            self.check_ready()

    def browse_sign(self):
        f = filedialog.askopenfilename(filetypes=[("Images", "*.png;*.jpg;*.jpeg")])
        if f:
            self.sign_img_path = f
            self.lbl_sign.config(text=os.path.basename(f), fg="black")
            self.processed_sign_img = self.make_transparent(f)
            self.render_signature_on_canvas()
            self.check_ready()

    def check_ready(self):
        if self.input_path and self.sign_img_path:
            self.btn_save.config(state="normal")

    # --- Preview Logic ---
    
    def load_preview_background(self):
        self.canvas.delete("all") # Clear everything
        
        if self.input_type == 'image':
            # โหลดรูปมาแสดงจริง
            img = Image.open(self.input_path)
            self.real_img_size = img.size
            
            # คำนวณ Scale ให้พอดีจอ (ไม่ให้ใหญ่เกิน 800px)
            max_preview_h = 800
            self.preview_scale = 1.0
            if img.size[1] > max_preview_h:
                self.preview_scale = max_preview_h / float(img.size[1])
            
            w_resized = int(img.size[0] * self.preview_scale)
            h_resized = int(img.size[1] * self.preview_scale)
            
            img_resized = img.resize((w_resized, h_resized), Image.Resampling.LANCZOS)
            self.tk_bg_image = ImageTk.PhotoImage(img_resized)
            
            # วางรูปที่ (0,0)
            self.canvas.config(scrollregion=(0, 0, w_resized, h_resized))
            self.canvas.create_image(0, 0, image=self.tk_bg_image, anchor="nw", tags="background")
            
        elif self.input_type == 'pdf':
            # PDF โชว์แค่กระดาษเปล่า A4
            # A4 point = 595 x 842 -> Scale มาโชว์บนจอ
            self.real_img_size = (595, 842) # สมมติเป็น A4 portrait
            self.preview_scale = 1.0 
            
            w = int(595 * self.preview_scale)
            h = int(842 * self.preview_scale)
            
            self.canvas.config(scrollregion=(0, 0, w, h))
            self.canvas.create_rectangle(20, 20, w, h, fill="white", outline="black", tags="background")
            self.canvas.create_text(w/2, h/2, text="(ตัวอย่างหน้ากระดาษ PDF)\nไฟล์จริงจะเป็นเอกสารของคุณ", fill="gray", justify="center")

        # ถ้าเคยเลือกลายเซ็นไว้แล้ว ให้วาดทับลงไปใหม่
        if self.processed_sign_img:
            self.render_signature_on_canvas()

    def render_signature_on_canvas(self):
        self.canvas.delete("movable")
        
        if not self.processed_sign_img: return

        # Resize ลายเซ็นสำหรับ Preview
        img = self.processed_sign_img.copy()
        base_width = 100
        w_percent = (base_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        img_resized = img.resize((base_width, h_size), Image.Resampling.LANCZOS)
        
        self.tk_sign_image = ImageTk.PhotoImage(img_resized)
        
        # วางกลางจอ
        start_x = 200
        start_y = 200
        
        # Group: Movable
        self.canvas.create_text(start_x, start_y - 30, text="สำเนาถูกต้อง", font=("Arial", 12, "bold"), tags="movable", fill="blue")
        self.canvas.create_image(start_x, start_y, image=self.tk_sign_image, tags="movable")
        self.canvas.create_text(start_x, start_y + 30, text=self.entry_date.get(), font=("Arial", 12), tags="movable", fill="blue")

    def update_preview_text(self, event=None):
        items = self.canvas.find_withtag("movable")
        # items[2] คือตัวที่ 3 ที่เรา create (คือวันที่)
        if len(items) >= 3:
            # เนื่องจาก Canvas return ID ไม่เรียงเสมอไป เราจะหาจาก type
            for item in items:
                if self.canvas.type(item) == 'text':
                    # เช็คว่าเป็นวันที่ (ตัวล่าง) หรือ สำเนาถูกต้อง (ตัวบน)
                    coords = self.canvas.coords(item)
                    # ตัวล่างจะมี Y มากกว่าตัวบน
                    # แต่เอาทริคง่ายๆ: อัปเดตตัวที่เป็น text แล้วมีค่าตรงกับ entry หรือไม่
                    pass 
            # Re-render ง่ายกว่า
            self.render_signature_on_canvas()

    # --- Dragging ---
    def on_drag_start(self, event):
        self.drag_data["x"] = self.canvas.canvasx(event.x)
        self.drag_data["y"] = self.canvas.canvasy(event.y)

    def on_drag_motion(self, event):
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        
        dx = cur_x - self.drag_data["x"]
        dy = cur_y - self.drag_data["y"]
        
        self.canvas.move("movable", dx, dy)
        
        self.drag_data["x"] = cur_x
        self.drag_data["y"] = cur_y

    # --- Save Logic ---
    def process_save(self):
        if self.input_type == 'pdf':
            self.save_as_pdf()
        else:
            self.save_as_image()

    def get_signature_position(self):
        """ คืนค่า (x, y) ของจุดกึ่งกลางลายเซ็น โดยแปลงกลับเป็น Scale จริงของเอกสาร """
        items = self.canvas.find_withtag("movable")
        img_item = None
        for item in items:
            if self.canvas.type(item) == 'image':
                img_item = item
                break
        
        if not img_item: return (0, 0)
        
        c_x, c_y = self.canvas.coords(img_item)
        
        # ปรับ Offset ถ้าเป็น PDF (เพราะ PDF ขอบเริ่มที่ (20,20) หรือตามที่เราวาด rect)
        offset_x = 0
        offset_y = 0
        if self.input_type == 'pdf':
             # ใน preview pdf เราวาด rect เริ่มที่ 20,20 ไม่ใช่ 0,0
             # แต่ PDF จริงเริ่มที่ 0,0 ดังนั้นต้องลบ offset นี้ออกไม่ได้ เพราะเราวางบน canvas
             pass

        real_x = (c_x - offset_x) / self.preview_scale
        real_y = (c_y - offset_y) / self.preview_scale
        
        return real_x, real_y

    def save_as_image(self):
        output_path = filedialog.asksaveasfilename(defaultextension=".jpg", filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png")])
        if not output_path: return

        try:
            # 1. เปิดภาพต้นฉบับ
            base_img = Image.open(self.input_path).convert("RGB")
            draw = ImageDraw.Draw(base_img)
            
            # 2. เตรียม Font (PIL ใช้ ImageFont)
            try:
                # ขนาดฟอนต์ต้องสัมพันธ์กับขนาดรูป (เอาสัก 2% ของความสูงรูป)
                font_size = int(base_img.size[1] * 0.025) 
                if font_size < 20: font_size = 20
                font = ImageFont.truetype(FONT_FILE, font_size)
            except:
                font = ImageFont.load_default()

            # 3. คำนวณตำแหน่ง
            real_x, real_y = self.get_signature_position()
            
            # 4. วาดลายเซ็น (PIL วาดจากมุมซ้ายบน)
            sig_w = int(base_img.size[0] * 0.15) # กว้าง 15% ของรูป
            w_percent = (sig_w / float(self.processed_sign_img.size[0]))
            sig_h = int((float(self.processed_sign_img.size[1]) * float(w_percent)))
            
            sig_resized = self.processed_sign_img.resize((sig_w, sig_h), Image.Resampling.LANCZOS)
            
            # ตำแหน่งวาง (ลบครึ่งนึงของขนาด เพื่อให้ (real_x, real_y) คือจุดกึ่งกลาง)
            paste_x = int(real_x - (sig_w / 2))
            paste_y = int(real_y - (sig_h / 2))
            
            # แปะรูป (ต้องใช้ mask เพื่อให้พื้นใส)
            base_img.paste(sig_resized, (paste_x, paste_y), sig_resized)
            
            # 5. วาดข้อความ (สีน้ำเงิน)
            text_color = (0, 0, 255)
            # สำเนาถูกต้อง (อยู่เหนือรูป)
            bbox = draw.textbbox((0, 0), "สำเนาถูกต้อง", font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            draw.text((real_x - text_w/2, paste_y - text_h - 5), "สำเนาถูกต้อง", font=font, fill=text_color)
            
            # วันที่ (อยู่ใต้รูป)
            date_text = self.entry_date.get()
            bbox = draw.textbbox((0, 0), date_text, font=font)
            text_w = bbox[2] - bbox[0]
            draw.text((real_x - text_w/2, paste_y + sig_h + 5), date_text, font=font, fill=text_color)

            base_img.save(output_path)
            messagebox.showinfo("สำเร็จ", "บันทึกไฟล์รูปภาพเรียบร้อย!")
            os.startfile(os.path.dirname(output_path))
            
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def save_as_pdf(self):
        output_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if not output_path: return

        try:
            real_x, real_y = self.get_signature_position()
            
            # แปลง Y ให้กลับหัว (PDF origin คือล่างซ้าย, Canvas คือบนซ้าย)
            # เราใช้ความสูง A4 มาตรฐาน
            pdf_h = 842 # A4 height points
            real_y_pdf = pdf_h - real_y

            # สร้าง Watermark PDF
            packet = io.BytesIO()
            can = pdf_canvas.Canvas(packet, pagesize=A4)
            
            try:
                pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_FILE))
                can.setFont(FONT_NAME, 16)
            except:
                can.setFont("Helvetica", 14)

            text_top = "สำเนาถูกต้อง"
            text_date = self.entry_date.get()
            
            # วาดลง PDF
            can.setFillColorRGB(0, 0, 1) # Blue
            can.drawCentredString(real_x, real_y_pdf + 40, text_top)
            
            img_buffer = io.BytesIO()
            self.processed_sign_img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            rl_image = ImageReader(img_buffer)
            
            sig_w = 100
            sig_h = 40
            can.drawImage(rl_image, real_x - (sig_w/2), real_y_pdf - (sig_h/2), width=sig_w, height=sig_h, mask='auto')
            
            can.drawCentredString(real_x, real_y_pdf - 25, text_date)
            can.save()
            packet.seek(0)

            # Merge
            watermark = PdfReader(packet)
            watermark_page = watermark.pages[0]
            reader = PdfReader(self.input_path)
            writer = PdfWriter()

            for page in reader.pages:
                page.merge_page(watermark_page)
                writer.add_page(page)

            with open(output_path, "wb") as f:
                writer.write(f)
            
            messagebox.showinfo("สำเร็จ", "บันทึกไฟล์ PDF เรียบร้อย!")
            os.startfile(os.path.dirname(output_path))

        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = DocumentSignerApp(root)
    root.mainloop()