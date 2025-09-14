import sys
import re
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QWidget, QPushButton, QLabel, QTextEdit, QListWidget,
                             QSplitter, QMessageBox, QListWidgetItem, QScrollArea)
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QBrush
import pytesseract
from PIL import Image, ImageGrab, ImageEnhance, ImageDraw
import cv2
import numpy
import csv
import json
from collections import defaultdict
from itertools import combinations

arknights_tags_by_category = {
    "Class": {
        "Guard": "近卫干员",
        "Sniper": "狙击干员",
        "Defender": "重装干员",
        "Medic": "医疗干员",
        "Supporter": "辅助干员",
        "Caster": "术师干员",
        "Specialist": "特种干员",
        "Vanguard": "先锋干员"
    },
    "Position": {
        "Melee": "近战位",
        "Ranged": "远程位"
    },
    "Qualification": {
        "Starter": "新手",
        "Senior Operator": "资深干员",
        "Top Operator": "高级资深干员"
    },
    "Affix": {
        "Crowd Control": "控场",
        "Nuker": "爆发",
        "Healing": "治疗",
        "Support": "支援",
        "DP-Recovery": "费用回复",
        "DPS": "输出",
        "Survival": "生存",
        "AoE": "群攻",
        "Defense": "防护",
        "Slow": "减速",
        "Debuff": "削弱",
        "Fast-Redeploy": "快速复活",
        "Shift": "位移",
        "Summon": "召唤",
        "Robot": "",
        "Elemental": "",
    }
}

class ScreenSelector(QWidget):
    selection_made = pyqtSignal(QRect)

    def __init__(self):
        super().__init__()
        os.makedirs("./temp", exist_ok=True)
        self.screenshot = ImageGrab.grab()
        screen_geometry = QApplication.primaryScreen().geometry()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setGeometry(screen_geometry)
        self.setCursor(Qt.CrossCursor)
        self.screenshot.save("./temp/temp_screenshot.png")
        self.background_pixmap = QPixmap("./temp/temp_screenshot.png")
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.selecting = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.background_pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        if self.selecting and not self.start_point.isNull() and not self.end_point.isNull():
            selection_rect = QRect(self.start_point, self.end_point).normalized()
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(selection_rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.drawPixmap(selection_rect, self.background_pixmap, selection_rect)
            pen = QPen(QColor(0, 150, 255), 2, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(selection_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.selecting:
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.selecting:
            self.selecting = False
            selection_rect = QRect(self.start_point, self.end_point).normalized()
            if selection_rect.width() > 10 and selection_rect.height() > 10:
                self.selection_made.emit(selection_rect)
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):
        if os.path.exists("./temp/temp_screenshot.png"):
            os.remove("./temp/temp_screenshot.png")
        super().closeEvent(event)

class ArknightsOCRApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_area = None
        self.setup_dark_theme()
        self.init_ui()

    def setup_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #2b2b2b; color: white; }
            QWidget { background-color: #2b2b2b; color: white; font-family: Consolas, monospace; }
            QPushButton { background-color: #404040; border: 2px solid #555; padding: 12px; border-radius: 6px; color: white; font-weight: bold; }
            QPushButton:hover { background-color: #505050; border-color: #666; }
            QPushButton:disabled { background-color: #333; color: #666; border-color: #444; }
            QTextEdit { background-color: #1e1e1e; border: 2px solid #555; color: #00ff00; font-family: Consolas, monospace; font-size: 11px; }
            QListWidget { background-color: #1e1e1e; border: 2px solid #555; color: white; }
            QListWidget::item { padding: 12px; margin: 2px; border-radius: 4px; }
            QListWidget::item:selected { background-color: #555; }
            QLabel { color: #ccc; font-weight: bold; padding: 4px; }
            QScrollArea { background-color: #1e1e1e; border: 2px solid #555; }
        """)

    def init_ui(self):
        self.setWindowTitle("Arknights Recruitment OCR(EN/CN Support)")
        self.setGeometry(100, 100, 1400, 900)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        button_layout = QHBoxLayout()
        self.select_btn = QPushButton("📸 Select Area")
        self.select_btn.clicked.connect(self.select_screen_area)
        self.run_btn = QPushButton("🔍 Run OCR")
        self.run_btn.clicked.connect(self.run_ocr_and_filter)
        self.run_btn.setEnabled(False)
        button_layout.addWidget(self.select_btn)
        button_layout.addWidget(self.run_btn)
        main_layout.addLayout(button_layout)
        self.status_label = QLabel("Select an area on screen to begin OCR analysis (Supports EN/CN)")
        main_layout.addWidget(self.status_label)
        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("📷 Original Selection:"))
        self.image_preview = QLabel()
        self.image_preview.setMinimumHeight(150)
        self.image_preview.setStyleSheet("border: 2px solid #555; background: #1e1e1e;")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setText("No image selected")
        left_layout.addWidget(self.image_preview)
        left_layout.addWidget(QLabel("🔍 OCR Block Analysis:"))
        self.analysis_preview_scroll = QScrollArea()
        self.analysis_preview_scroll.setMinimumHeight(200)
        self.analysis_preview_scroll.setStyleSheet("border: 2px solid #555; background: #1e1e1e;")
        self.analysis_preview_scroll.setWidgetResizable(True)
        self.analysis_preview_label = QLabel("Run OCR to see block analysis")
        self.analysis_preview_label.setAlignment(Qt.AlignCenter)
        self.analysis_preview_label.setScaledContents(False)
        self.analysis_preview_scroll.setWidget(self.analysis_preview_label)
        left_layout.addWidget(self.analysis_preview_scroll)
        left_layout.addWidget(QLabel("📝 Raw OCR Output:"))
        self.ocr_text = QTextEdit()
        self.ocr_text.setMaximumHeight(120)
        self.ocr_text.setPlaceholderText("OCR raw text will appear here...")
        left_layout.addWidget(self.ocr_text)
        left_layout.addWidget(QLabel("🏷️ Detected Tags:"))
        self.detected_tags = QTextEdit()
        self.detected_tags.setMaximumHeight(80)
        self.detected_tags.setPlaceholderText("Parsed tags will appear here...")
        left_layout.addWidget(self.detected_tags)
        splitter.addWidget(left_widget)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(QLabel("⭐ Matching Operators:"))
        self.operators_list = QListWidget()
        right_layout.addWidget(self.operators_list)
        splitter.addWidget(right_widget)
        splitter.setSizes([700, 700])
        main_layout.addWidget(splitter)

    def select_screen_area(self):
        self.hide()
        QTimer.singleShot(200, self.show_screen_selector)

    def show_screen_selector(self):
        self.screen_selector = ScreenSelector()
        self.screen_selector.selection_made.connect(self.on_area_selected)
        self.screen_selector.show()

    def on_area_selected(self, rect):
        self.selected_area = rect
        self.show()
        self.run_btn.setEnabled(True)
        self.status_label.setText(f"📐 Area selected: {rect.width()}×{rect.height()} pixels at ({rect.x()}, {rect.y()})")
        screenshot = ImageGrab.grab(bbox=(
            rect.x(), rect.y(),
            rect.x() + rect.width(),
            rect.y() + rect.height()
        ))
        screenshot.save("./temp/preview.png")
        pixmap = QPixmap("./temp/preview.png")
        scaled_pixmap = pixmap.scaled(300, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_preview.setPixmap(scaled_pixmap)

    def preprocess_image_for_ocr(self, image):
        if image.mode != 'L':
            image = image.convert('L')
        width, height = image.size
        image = image.resize((width * 2, height * 2), Image.LANCZOS)
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        return image
    
    def auto_crop_image_adaptive(self, image_pillow):
        try:
            img_np_rgb = numpy.array(image_pillow)
            img_np_bgr = cv2.cvtColor(img_np_rgb, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(img_np_bgr, cv2.COLOR_BGR2GRAY)
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest_contour = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest_contour)
                padding = -10
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(img_np_bgr.shape[1] - x, w + 2 * padding)
                h = min(img_np_bgr.shape[0] - y, h + 2 * padding)
                cropped_img_np = img_np_bgr[y:y+h, x:x+w]
                cropped_img_rgb = cv2.cvtColor(cropped_img_np, cv2.COLOR_BGR2RGB)
                cropped_pillow_image = Image.fromarray(cropped_img_rgb)
                return cropped_pillow_image
            return image_pillow
        except Exception as e:
            print(f"Auto-crop failed: {e}")
            return image_pillow
    
    def run_ocr_multilang(self, image, lang_configs):
        all_results = []
        
        for lang_name, config in lang_configs.items():
            try:
                result = pytesseract.image_to_string(image, config=config).strip()
                if result:
                    all_results.append(f"[{lang_name}] {result}")
            except Exception as e:
                all_results.append(f"[{lang_name}] Error: {str(e)}")
        
        return all_results
    
    def run_ocr_and_filter(self):
        if not self.selected_area:
            return
        try:
            self.status_label.setText("🔄 Running comprehensive multi-language OCR analysis...")
            QApplication.processEvents()
            screenshot = ImageGrab.grab(bbox=(
                self.selected_area.x(), self.selected_area.y(),
                self.selected_area.x() + self.selected_area.width(),
                self.selected_area.y() + self.selected_area.height()
            ))
            analysis_image = screenshot.copy()
            if analysis_image.mode != 'RGB':
                analysis_image = analysis_image.convert('RGB')
            draw = ImageDraw.Draw(analysis_image)

            width, height = screenshot.size
            num_cols = 3
            num_rows = 2
            block_width = width / num_cols
            block_height = height / num_rows
            all_detected_text = []
            ocr_results = []
            
            lang_configs = {
                "ENG": '--psm 6 -l eng -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_',
                "CHI": '--psm 6 -l chi_sim',
            }
            
            split_block_color = (0, 255, 0)
            split_block_outline_width = 3

            for row in range(num_rows):
                for col in range(num_cols):
                    x1 = int(col * block_width)
                    y1 = int(row * block_height)
                    x2 = int((col + 1) * block_width)
                    y2 = int((row + 1) * block_height)
                    draw.rectangle([x1, y1, x2, y2], outline=split_block_color, width=split_block_outline_width)
                    block_image = screenshot.crop((x1, y1, x2, y2))
                    block_filename = os.path.join("./temp/", f"block_r{row}_c{col}.png")
                    
                    processed_image = self.auto_crop_image_adaptive(block_image)
                    processed_image = self.preprocess_image_for_ocr(processed_image)
                    processed_image.save(block_filename)
                    print(f"Saved debug image to {block_filename}")
                    
                    multilang_results = self.run_ocr_multilang(processed_image, lang_configs)
                    
                    block_texts = []
                    for result in multilang_results:
                        if not result.startswith("[") or "Error" not in result:
                            if "] " in result:
                                text = result.split("] ", 1)[1]
                                if text and text not in block_texts:
                                    block_texts.append(text)
                                    all_detected_text.append(text)
                    
                    ocr_results.append(f"Block ({row+1},{col+1}):")
                    for result in multilang_results:
                        ocr_results.append(f"  {result}")
            
            analysis_image.save("./temp/analysis.png")
            analysis_pixmap = QPixmap("./temp/analysis.png")
            self.analysis_preview_label.setPixmap(analysis_pixmap)
            self.analysis_preview_label.setFixedSize(analysis_pixmap.size())

            combined_text = " ".join(all_detected_text)
            
            ocr_output = f"MULTI-LANGUAGE SPLIT-BLOCK OCR RESULTS:\n"
            for result in ocr_results:
                ocr_output += f"{result}\n"
            ocr_output += f"\nCOMBINED TEXT: {combined_text}"
            self.ocr_text.setPlainText(ocr_output)

            detected_tags = self.extract_tags_from_text(combined_text)
            self.detected_tags.setPlainText(", ".join(detected_tags) if detected_tags else "No recruitment tags detected")
            filtered_operators = self.get_operators_by_tags(detected_tags)
            self.display_filtered_operators(filtered_operators)

            self.status_label.setText(f"✅ Multi-language analysis complete! {len(all_detected_text)} text blocks found, {len(detected_tags)} tags detected, {len(filtered_operators)} combinations found")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"OCR failed: {str(e)}")
            self.status_label.setText(f"❌ OCR failed: {str(e)}")
            import traceback
            traceback.print_exc()

    def extract_tags_from_text(self, text):
        detected_tags = []
        text_clean = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text.upper())

        fuzzy_matches = {
            "CUARD": "Guard", "GUARD": "Guard", "SNIPER": "Sniper",
            "DEFENDER": "Defender", "MEDIC": "Medic", "SUPPORTER": "Supporter",
            "CASTER": "Caster", "SPECIALIST": "Specialist", "VANGUARD": "Vanguard",
            "MELEE": "Melee", "RANGED": "Ranged", "近卫": "Guard",
            "狙击": "Sniper", "重装": "Defender", "医疗": "Medic",
            "辅助": "Supporter", "术师": "Caster", "特种": "Specialist",
            "先锋": "Vanguard", "近战": "Melee", "远程": "Ranged"
        }

        for category, tags in arknights_tags_by_category.items():
            for eng_tag, chi_tag in tags.items():
                if eng_tag.upper() in text_clean:
                    detected_tags.append(eng_tag)
                elif chi_tag and chi_tag in text:
                    detected_tags.append(eng_tag)

        for fuzzy_text, correct_tag in fuzzy_matches.items():
            if fuzzy_text in text_clean or fuzzy_text in text:
                detected_tags.append(correct_tag)

        seen = set()
        ordered_unique_tags = []
        for tag in detected_tags:
            if tag not in seen:
                seen.add(tag)
                ordered_unique_tags.append(tag)

        return ordered_unique_tags

    def get_operators_by_tags(self, input_tags):
        operators = []
        with open('./data/operatordata_en.csv', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                operators.append({
                    'name': row['name_en'],
                    'rarity': int(row['rarity']),
                    'tags': [t.strip() for t in row['tags_en'].split(';')]
                })

        grouped_by_tags = defaultdict(list)

        for op in operators:
            match_tags = sorted([t for t in op['tags'] if t in input_tags])

            if match_tags:
                for r in range(1, len(match_tags) + 1):
                    for combo in combinations(match_tags, r):
                        grouped_by_tags[tuple(combo)].append(op)

        result = []
        for tags_tuple, ops_list in grouped_by_tags.items():
            ops_list.sort(key=lambda x: x['rarity'], reverse=True)
            result.append({
                'match_count': len(tags_tuple),
                'tags': list(tags_tuple),
                'operators': ops_list
            })

        result.sort(key=lambda x: x['match_count'], reverse=True)

        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    def display_filtered_operators(self, grouped_operators):
        self.operators_list.clear()
        RARITY_COLOR = {
            1: '#FFFFFF',
            2: '#9E9E1E',
            3: '#0398D0',
            4: '#CFB6CF',
            5: '#FFE916',
            6: "#FF8400"
        }
        
        for group in grouped_operators:
            container_widget = QWidget()
            layout = QVBoxLayout(container_widget)
            
            tags_label = QLabel(f"Tags: {', '.join(group['tags'])}")
            tags_label.setWordWrap(True)
            layout.addWidget(tags_label)

            operator_html = "Operator: "
            for op in group['operators']:
                color = RARITY_COLOR.get(op['rarity'], "#FFFFFF")
                operator_html += f'<span style="color:{color}">{op["name"]}</span>, '
            operator_html = operator_html.rstrip(", ")

            operator_label = QLabel()
            operator_label.setText(operator_html)
            operator_label.setTextFormat(Qt.RichText)
            operator_label.setWordWrap(True)
            layout.addWidget(operator_label)

            list_item = QListWidgetItem()
            self.operators_list.addItem(list_item)
            self.operators_list.setItemWidget(list_item, container_widget)
            list_item.setSizeHint(container_widget.sizeHint())

def main():
    app = QApplication(sys.argv)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    try:
        pytesseract.get_tesseract_version()
    except:
        QMessageBox.critical(None, "Error", "Tesseract OCR not found! Please install it with Chinese language support.")
        sys.exit(1)
    window = ArknightsOCRApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()