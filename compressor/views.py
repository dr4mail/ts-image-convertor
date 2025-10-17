"""
Views для веб-сервиса сжатия изображений с авторизацией
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.conf import settings
from django.utils import timezone
from pathlib import Path
import uuid
import json
import threading
import os

from .compressor_engine import WebCompressor
from .models import CompressionSession, CompressionFile


def login_view(request):
    """Страница входа"""
    if request.user.is_authenticated:
        return redirect('compressor:index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('compressor:index')
        else:
            return render(request, 'compressor/login.html', {
                'error': 'Invalid username or password'
            })
    
    return render(request, 'compressor/login.html')


def logout_view(request):
    """Выход"""
    logout(request)
    return redirect('compressor:login')


@login_required
def index(request):
    """Главная страница"""
    return render(request, 'compressor/index.html')


@login_required
def profile(request):
    """Личный кабинет с историей"""
    sessions = CompressionSession.objects.filter(user=request.user)
    downloaded_sessions = sessions.filter(status='downloaded')
    
    # Статистика (только по скачанным сессиям)
    total_sessions = sessions.count()
    files_processed = sum(s.files_successful for s in downloaded_sessions)
    megabytes_processed = sum(s.total_original_mb for s in downloaded_sessions)
    total_saved_mb = sum(s.total_original_mb - s.total_compressed_mb for s in downloaded_sessions)
    
    context = {
        'sessions': sessions[:50],  # Последние 50 сессий
        'stats': {
            'total_sessions': total_sessions,
            'files_processed': files_processed,
            'megabytes_processed': round(megabytes_processed, 1),
            'total_saved_mb': round(total_saved_mb, 1)
        }
    }
    
    return render(request, 'compressor/profile.html', context)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def upload_files(request):
    """Загрузка файлов"""
    try:
        files = request.FILES.getlist('files')
        prefix = request.POST.get('prefix', '').strip()
        settings_json = request.POST.get('settings', '{}')
        
        # Парсим настройки
        try:
            compression_settings = json.loads(settings_json)
        except:
            compression_settings = {}
        
        # Валидация количества файлов
        if len(files) > settings.MAX_FILES_COUNT:
            return JsonResponse({
                'error': f'Maximum {settings.MAX_FILES_COUNT} files allowed'
            }, status=400)
        
        if not files:
            return JsonResponse({'error': 'No files uploaded'}, status=400)
        
        # Создаем сессию
        session_id = str(uuid.uuid4())
        session_path = Path(settings.TEMP_ROOT) / session_id
        uploads_path = session_path / 'uploads'
        uploads_path.mkdir(parents=True, exist_ok=True)
        
        # Валидация и сохранение файлов
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        file_list = []
        
        for file in files:
            ext = Path(file.name).suffix.lower()
            if ext not in allowed_extensions:
                return JsonResponse({
                    'error': f'File {file.name} has unsupported format'
                }, status=400)
            
            if file.size > settings.MAX_UPLOAD_SIZE:
                return JsonResponse({
                    'error': f'File {file.name} exceeds {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB limit'
                }, status=400)
            
            safe_filename = "".join(c for c in file.name if c.isalnum() or c in ('_', '-', '.')).strip()
            if not safe_filename:
                safe_filename = f"file_{uuid.uuid4().hex[:8]}{ext}"
            
            filepath = uploads_path / safe_filename
            with open(filepath, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            
            file_list.append({
                'name': file.name,
                'size': file.size,
                'size_mb': round(file.size / (1024 * 1024), 2)
            })
        
        # Создаем запись в БД
        db_session = CompressionSession.objects.create(
            user=request.user,
            session_id=session_id,
            prefix=prefix,
            archive_name=prefix if prefix else 'Archive',
            status='uploaded',
            files_count=len(file_list),
            compression_quality=compression_settings.get('quality'),
            compression_max_dimension=compression_settings.get('max_dimension'),
            compression_no_resize=compression_settings.get('no_resize', False)
        )
        
        # Сохраняем метаданные для процесса сжатия
        session_meta = {
            'session_id': session_id,
            'prefix': prefix,
            'compression_settings': compression_settings,
            'files': file_list,
            'status': 'uploaded'
        }
        
        with open(session_path / 'meta.json', 'w') as f:
            json.dump(session_meta, f, indent=2)
        
        return JsonResponse({
            'session_id': session_id,
            'uploaded_count': len(file_list),
            'files': file_list,
            'total_size_mb': round(sum(f['size'] for f in file_list) / (1024 * 1024), 2)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def compress_images(request, session_id):
    """Запуск сжатия"""
    try:
        # Проверяем что сессия принадлежит пользователю
        db_session = CompressionSession.objects.get(
            session_id=session_id,
            user=request.user
        )
        
        session_path = Path(settings.TEMP_ROOT) / session_id
        
        if not session_path.exists():
            return JsonResponse({'error': 'Session not found'}, status=404)
        
        meta_file = session_path / 'meta.json'
        if not meta_file.exists():
            return JsonResponse({'error': 'Session metadata not found'}, status=404)
        
        with open(meta_file, 'r') as f:
            meta = json.load(f)
        
        if db_session.status == 'processing':
            return JsonResponse({'error': 'Already processing'}, status=400)
        
        # Обновляем статус
        db_session.status = 'processing'
        db_session.save()
        
        meta['status'] = 'processing'
        with open(meta_file, 'w') as f:
            json.dump(meta, f, indent=2)
        
        # Запускаем сжатие в отдельном потоке
        def compress_task():
            try:
                compressor = WebCompressor(
                    session_path,
                    prefix=meta['prefix'],
                    compression_settings=meta['compression_settings']
                )
                
                def progress_update(data):
                    progress_file = session_path / 'progress.json'
                    with open(progress_file, 'w') as f:
                        json.dump(data, f, indent=2)
                
                compressor.progress_callback = progress_update
                
                uploads_path = session_path / 'uploads'
                files = list(uploads_path.glob('*'))
                
                if not files:
                    raise Exception("No files to compress")
                
                # Сжимаем
                results = compressor.compress_batch(files)
                
                # Создаем архив
                archive_name = meta['prefix'] if meta['prefix'] else 'Archive'
                archive_path = compressor.create_archive(archive_name)
                
                results['archive_name'] = archive_path.name
                results['archive_size_mb'] = round(archive_path.stat().st_size / (1024*1024), 2)
                results['status'] = 'completed'
                
                for cat, stats in results['categories'].items():
                    if stats['orig'] > 0:
                        stats['savings'] = round((1 - stats['comp'] / stats['orig']) * 100, 1)
                
                with open(session_path / 'results.json', 'w') as f:
                    json.dump(results, f, indent=2)
                
                # Обновляем БД
                db_session.status = 'completed'
                db_session.files_successful = results['successful']
                db_session.files_failed = results['failed']
                db_session.total_original_mb = round(results['total_original_mb'], 2)
                db_session.total_compressed_mb = round(results['total_compressed_mb'], 2)
                
                if results['total_original_mb'] > 0:
                    db_session.savings_percent = round(
                        (1 - results['total_compressed_mb'] / results['total_original_mb']) * 100, 1
                    )
                
                db_session.completed_at = timezone.now()
                db_session.save()
                
                # Сохраняем информацию о файлах
                for file_info in results['files']:
                    CompressionFile.objects.create(
                        session=db_session,
                        original_name=file_info['name'],
                        output_name=file_info['output_name'],
                        original_size_mb=file_info['original_mb'],
                        compressed_size_mb=file_info['compressed_mb'],
                        savings_percent=file_info['savings'],
                        category=file_info.get('category', '')
                    )
                
                meta['status'] = 'completed'
                with open(meta_file, 'w') as f:
                    json.dump(meta, f, indent=2)
                    
            except Exception as e:
                error_data = {'status': 'error', 'error': str(e)}
                with open(session_path / 'results.json', 'w') as f:
                    json.dump(error_data, f, indent=2)
                
                db_session.status = 'error'
                db_session.error_message = str(e)
                db_session.save()
                
                meta['status'] = 'error'
                meta['error'] = str(e)
                with open(meta_file, 'w') as f:
                    json.dump(meta, f, indent=2)
        
        thread = threading.Thread(target=compress_task)
        thread.daemon = True
        thread.start()
        
        return JsonResponse({'status': 'started', 'message': 'Compression started'})
        
    except CompressionSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found or access denied'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_status(request, session_id):
    """Получить статус обработки"""
    try:
        # Проверяем доступ
        db_session = CompressionSession.objects.get(
            session_id=session_id,
            user=request.user
        )
        
        session_path = Path(settings.TEMP_ROOT) / session_id
        
        if not session_path.exists():
            return JsonResponse({'error': 'Session not found'}, status=404)
        
        progress_file = session_path / 'progress.json'
        if progress_file.exists():
            with open(progress_file, 'r') as f:
                progress_data = json.load(f)
        else:
            progress_data = {'progress': 0, 'stage': 'waiting'}
        
        results_file = session_path / 'results.json'
        if results_file.exists():
            with open(results_file, 'r') as f:
                results = json.load(f)
            progress_data['results'] = results
            progress_data['stage'] = 'completed'
        
        return JsonResponse(progress_data)
        
    except CompressionSession.DoesNotExist:
        return JsonResponse({'error': 'Access denied'}, status=403)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def download_archive(request, session_id):
    """Скачать архив"""
    try:
        db_session = CompressionSession.objects.get(
            session_id=session_id,
            user=request.user
        )
        
        session_path = Path(settings.TEMP_ROOT) / session_id
        archives_path = session_path / 'archives'
        
        if not archives_path.exists():
            return HttpResponse('Archive not found', status=404)
        
        archives = list(archives_path.glob('*.zip'))
        if not archives:
            return HttpResponse('Archive not found', status=404)
        
        archive_path = archives[0]
        
        # Отмечаем как скачанное
        db_session.mark_as_downloaded()
        
        response = FileResponse(
            open(archive_path, 'rb'),
            as_attachment=True,
            filename=archive_path.name
        )
        return response
        
    except CompressionSession.DoesNotExist:
        return HttpResponse('Access denied', status=403)
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)


@login_required
@require_http_methods(["GET"])
def get_summary(request, session_id):
    """Получить итоговую статистику"""
    try:
        db_session = CompressionSession.objects.get(
            session_id=session_id,
            user=request.user
        )
        
        session_path = Path(settings.TEMP_ROOT) / session_id
        results_file = session_path / 'results.json'
        
        if not results_file.exists():
            return JsonResponse({'error': 'Results not found'}, status=404)
        
        with open(results_file, 'r') as f:
            results = json.load(f)
        
        return JsonResponse(results)
        
    except CompressionSession.DoesNotExist:
        return JsonResponse({'error': 'Access denied'}, status=403)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)