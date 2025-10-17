"""
Движок сжатия изображений для веб-сервиса
Адаптированная версия HybridImageCompressor
"""

from PIL import Image, ImageOps
from pathlib import Path
import zipfile
import json


class WebCompressor:
    def __init__(self, session_path, prefix="", compression_settings=None):
        """
        compression_settings = {
            'quality': int or None,  # None = auto
            'max_dimension': int or None,  # None = auto
            'no_resize': bool  # True = keep original
        }
        """
        self.session_path = Path(session_path)
        self.uploads_path = self.session_path / "uploads"
        self.compressed_path = self.session_path / "compressed"
        self.archives_path = self.session_path / "archives"
        
        self.compressed_path.mkdir(exist_ok=True)
        self.archives_path.mkdir(exist_ok=True)
        
        self.prefix = prefix
        self.progress_callback = None
        
        # Целевые размеры
        self.target_max_size_mb = 1.0
        self.target_min_size_kb = 50
        
        # Применяем настройки пользователя
        settings = compression_settings or {}
        
        if settings.get('quality'):
            self.override_quality = settings['quality']
        else:
            self.override_quality = None
            
        if settings.get('no_resize'):
            self.override_max_dimension = None
        elif settings.get('max_dimension'):
            self.override_max_dimension = settings['max_dimension']
        else:
            self.override_max_dimension = 'auto'
    
    def get_file_size_mb(self, file_path):
        """Получить размер файла в МБ"""
        return file_path.stat().st_size / (1024 * 1024)
    
    def get_file_size_kb(self, file_path):
        """Получить размер файла в КБ"""
        return file_path.stat().st_size / 1024
    
    def analyze_image(self, image_path):
        """Полный анализ изображения"""
        file_size_mb = self.get_file_size_mb(image_path)
        
        with Image.open(image_path) as img:
            width, height = img.size
            max_dimension = max(width, height)
            aspect_ratio = width / height
            format_type = img.format
            
            is_whatsapp = "whatsapp" in image_path.name.lower()
            is_png_with_transparency = format_type == 'PNG' and img.mode in ('RGBA', 'LA')
            
            analysis = {
                'file_size_mb': file_size_mb,
                'width': width,
                'height': height,
                'max_dimension': max_dimension,
                'aspect_ratio': aspect_ratio,
                'format': format_type,
                'is_whatsapp': is_whatsapp,
                'is_png_transparent': is_png_with_transparency
            }
            
        return analysis
    
    def determine_compression_category(self, analysis):
        """Определить категорию сжатия"""
        size_mb = analysis['file_size_mb']
        max_dim = analysis['max_dimension']
        
        # Специальные случаи
        if analysis['is_whatsapp'] and size_mb < 0.5:
            result = {
                'category': 'WhatsApp',
                'quality': 90,
                'max_dimension': None,
                'description': 'WhatsApp (already optimized)',
                'aggressive': False
            }
        # Основная логика категоризации
        elif size_mb > 10 or max_dim > 3000:
            result = {
                'category': 'A - Huge',
                'quality': 60,
                'max_dimension': 1200,
                'description': 'Aggressive compression',
                'aggressive': True
            }
        elif size_mb > 2 or max_dim > 2000:
            result = {
                'category': 'B - Large',
                'quality': 75,
                'max_dimension': 1400,
                'description': 'Medium compression',
                'aggressive': False
            }
        elif size_mb > 0.5 or max_dim > 1000:
            result = {
                'category': 'C - Medium',
                'quality': 85,
                'max_dimension': 1600,
                'description': 'Light compression',
                'aggressive': False
            }
        else:
            result = {
                'category': 'D - Small',
                'quality': 90,
                'max_dimension': None,
                'description': 'Minimal compression',
                'aggressive': False
            }
        
        # Применяем override если заданы
        if self.override_quality is not None:
            result['quality'] = self.override_quality
            result['description'] = f"Custom quality {self.override_quality}%"
        
        if self.override_max_dimension != 'auto':
            result['max_dimension'] = self.override_max_dimension
            if self.override_max_dimension is None:
                result['description'] += " (no resize)"
            else:
                result['description'] += f" (max {self.override_max_dimension}px)"
        
        return result
    
    def resize_proportional(self, image, max_dimension):
        """Строго пропорциональное изменение размера"""
        if max_dimension is None:
            return image
            
        width, height = image.size
        current_max = max(width, height)
        
        if current_max <= max_dimension:
            return image
        
        scale_factor = max_dimension / current_max
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    def compress_iteratively(self, image, base_quality, output_path, target_size_mb):
        """Итеративное сжатие"""
        quality = base_quality
        attempts = 0
        max_attempts = 5
        
        while attempts < max_attempts:
            image.save(
                output_path,
                'JPEG',
                quality=quality,
                optimize=True,
                progressive=True
            )
            
            current_size_mb = self.get_file_size_mb(output_path)
            
            if current_size_mb <= target_size_mb or quality <= 30:
                break
                
            quality = max(30, quality - 10)
            attempts += 1
            
        return current_size_mb, quality
    
    def compress_image(self, input_path):
        """Сжать одно изображение"""
        try:
            analysis = self.analyze_image(input_path)
            settings = self.determine_compression_category(analysis)
            
            with Image.open(input_path) as img:
                # Автоповорот по EXIF
                img = ImageOps.exif_transpose(img)
                
                # Обработка PNG с прозрачностью
                if analysis['is_png_transparent']:
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Изменение размера
                img = self.resize_proportional(img, settings['max_dimension'])
                
                # Имя выходного файла с префиксом
                if self.prefix:
                    output_name = f"{self.prefix}_{input_path.stem}_compressed.jpg"
                else:
                    output_name = f"{input_path.stem}_compressed.jpg"
                
                output_path = self.compressed_path / output_name
                
                # Сжатие
                if settings['aggressive'] and analysis['file_size_mb'] > 5:
                    final_size_mb, final_quality = self.compress_iteratively(
                        img, settings['quality'], output_path, self.target_max_size_mb
                    )
                else:
                    img.save(
                        output_path,
                        'JPEG',
                        quality=settings['quality'],
                        optimize=True,
                        progressive=True
                    )
                    final_size_mb = self.get_file_size_mb(output_path)
                
                # Проверка: не стал ли файл больше
                if final_size_mb > analysis['file_size_mb']:
                    output_path.unlink()
                    import shutil
                    if self.prefix:
                        final_output_path = self.compressed_path / f"{self.prefix}_{input_path.stem}_original{input_path.suffix}"
                    else:
                        final_output_path = self.compressed_path / f"{input_path.stem}_original{input_path.suffix}"
                    shutil.copy2(input_path, final_output_path)
                    final_size_mb = analysis['file_size_mb']
                
                return True, analysis['file_size_mb'], final_size_mb, settings['category']
                
        except Exception as e:
            print(f"Error compressing {input_path.name}: {e}")
            return False, 0, 0, None
    
    def compress_batch(self, file_list):
        """Сжать батч файлов с прогрессом"""
        total = len(file_list)
        results = {
            'successful': 0,
            'failed': 0,
            'total_original_mb': 0,
            'total_compressed_mb': 0,
            'files': [],
            'categories': {}
        }
        
        for idx, file_path in enumerate(file_list):
            # Уведомляем о прогрессе
            if self.progress_callback:
                self.progress_callback({
                    'progress': int((idx / total) * 100),
                    'current_file': file_path.name,
                    'stage': 'compressing',
                    'index': idx + 1,
                    'total': total
                })
            
            # Сжимаем файл
            success, orig_mb, comp_mb, category = self.compress_image(file_path)
            
            if success:
                results['successful'] += 1
                results['total_original_mb'] += orig_mb
                results['total_compressed_mb'] += comp_mb
                
                if self.prefix:
                    output_name = f"{self.prefix}_{file_path.stem}_compressed.jpg"
                else:
                    output_name = f"{file_path.stem}_compressed.jpg"
                
                results['files'].append({
                    'name': file_path.name,
                    'output_name': output_name,
                    'original_mb': round(orig_mb, 2),
                    'compressed_mb': round(comp_mb, 2),
                    'savings': round((1 - comp_mb/orig_mb) * 100, 1) if orig_mb > 0 else 0,
                    'category': category
                })
                
                # Статистика по категориям
                if category:
                    if category not in results['categories']:
                        results['categories'][category] = {'count': 0, 'orig': 0, 'comp': 0}
                    results['categories'][category]['count'] += 1
                    results['categories'][category]['orig'] += orig_mb
                    results['categories'][category]['comp'] += comp_mb
            else:
                results['failed'] += 1
            
            # Удаляем исходный файл после сжатия
            try:
                file_path.unlink()
            except:
                pass
        
        # Финальный прогресс
        if self.progress_callback:
            self.progress_callback({
                'progress': 100,
                'stage': 'archiving',
                'current_file': 'Creating archive...'
            })
        
        return results
    
    def create_archive(self, archive_name=None):
        """Создать ZIP архив"""
        if not archive_name:
            archive_name = "Archive"
        
        # Санитизация имени
        archive_name = "".join(c for c in archive_name if c.isalnum() or c in (' ', '-', '_')).strip()
        if not archive_name:
            archive_name = "Archive"
        
        archive_path = self.archives_path / f"{archive_name}.zip"
        
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in self.compressed_path.glob('*'):
                zipf.write(file, file.name)
        
        # Удаляем сжатые файлы после архивации
        for file in self.compressed_path.glob('*'):
            file.unlink()
        
        return archive_path