import os
import uuid
import io
from minio.error import S3Error
import re
from processpdf.model_cache import (
    configure_local_model_environment,
    ensure_required_local_models,
    get_compatible_text_recognition_version,
)
from processpdf.surya_tokenizer_compat import apply_surya_tokenizer_compat


def process_pdf_with_marker(pdf_path, minio_client, bucket_name, image_prefix, minio_endpoint_for_url, marker_config=None):
    """
    使用marker处理PDF，提取Markdown和图片，将图片上传到MinIO并更新Markdown中的链接。
    仅使用本地已存在的模型，不进行任何下载。

    参数:
    - pdf_path: PDF文件路径
    - minio_client: Initialized Minio client object
    - bucket_name: MinIO bucket name
    - image_prefix: Prefix for image object names in MinIO bucket
    - minio_endpoint_for_url: Full MinIO endpoint URL for public URLs
    - marker_config: Optional dictionary for marker configuration

    返回:
    - updated_markdown: 更新了图片链接的Markdown文本
    - uploaded_images: 上传到MinIO的图片信息列表
    """
    # 统一 Marker / HuggingFace / datalab 的缓存根目录，强制只读本地模型。
    cache_dir = configure_local_model_environment()
    ensure_required_local_models(cache_dir)
    recognition_version = get_compatible_text_recognition_version(cache_dir)
    apply_surya_tokenizer_compat()
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser
    from marker.output import text_from_rendered

    print(f"使用 marker 处理PDF（仅本地模型）: {pdf_path}")
    print(f"本地模型缓存根目录: {cache_dir}")
    if recognition_version:
        print(f"使用本地 text_recognition 版本: {recognition_version}")

    if marker_config is None:
        marker_config = {
            "output_format": "markdown",
            "format_lines": True,
        }
    
    # 1. 使用 marker 处理 PDF
    config_parser = ConfigParser(marker_config)
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
    )
    rendered = converter(pdf_path)
    markdown, _, images = text_from_rendered(rendered)
    print(f"Marker 处理完成，提取到 {len(images)} 张图片。")

    uploaded_images = []
    image_url_mapping = {}

    # 2. 上传图片到 MinIO
    print(f"开始上传图片到 MinIO Bucket: {bucket_name}")
    for original_path, pil_image in images.items():
        try:
            # 生成唯一文件名
            base_name, ext = os.path.splitext(original_path)
            if base_name.startswith('_'):
                base_name = base_name[1:]
            unique_id = uuid.uuid4().hex[:8]
            new_filename = f"{base_name}_{unique_id}{ext}"
            
            image_object_name = f"{image_prefix.strip('/')}/{new_filename}"

            # 将 PIL Image 转换为 bytes
            img_bytes_io = io.BytesIO()
            image_format = ext[1:].upper()
            if image_format in ['JPG', 'JPEG']:
                if pil_image.mode == 'RGBA':
                    pil_image = pil_image.convert('RGB')
                pil_image.save(img_bytes_io, format='JPEG')
            else: # 默认使用 PNG
                image_format = 'PNG'
                pil_image.save(img_bytes_io, format='PNG')
            
            image_bytes = img_bytes_io.getvalue()
            image_size = len(image_bytes)
            content_type = f'image/{image_format.lower()}'

            # 上传到 MinIO
            result = minio_client.put_object(
                bucket_name,
                image_object_name,
                io.BytesIO(image_bytes),
                length=image_size,
                content_type=content_type
            )
            print(f"  - 成功上传: {result.object_name}")

            # 构建 MinIO 公共 URL
            image_url = f"{minio_endpoint_for_url}/{bucket_name}/{image_object_name}"
            image_url_mapping[original_path] = image_url

            img_info = {
                "original_filename": original_path,
                "new_filename": new_filename,
                "object_name": result.object_name,
                "url": image_url,
                "size": image_size,
            }
            uploaded_images.append(img_info)

        except S3Error as s3_err:
            print(f"  - 错误: 上传图片 {original_path} 到 MinIO 失败: {s3_err}")
        except Exception as e:
            print(f"  - 错误: 处理图片 {original_path} 时发生未知错误: {e}")

    # 3. 更新 Markdown 中的图片链接
    updated_markdown = str(markdown)
    print("更新Markdown中的图片链接...")
    for original_path, new_url in image_url_mapping.items():
        updated_markdown = updated_markdown.replace(f"({original_path})", f"({new_url})")
    
    print("Markdown链接更新完成。")
    return updated_markdown, uploaded_images


def upload_image_to_minio(minio_client, bucket_name, image_prefix, minio_endpoint_for_url, image_name, image_stream):
    try:
        print(f"上传图片到 MinIO: {image_name}")
        minio_client.put_object(
            bucket_name,
            image_name,
            data=image_stream,
            length=len(image_stream.getvalue()),
            content_type="image/png"
        )
        print(f"图片上传成功: {image_name}")
        
        # 构建可公开访问的URL
        image_url = f"{minio_endpoint_for_url}/{bucket_name}/{image_name}"
        return image_name, image_url

    except Exception as e:
        print(f"上传图片失败: {e}")
        return image_name, None

# 移除main函数中对RAGService的依赖，因为这个文件现在是作为一个库模块被调用
if __name__ == '__main__':
    # 这是一个很好的实践，可以在直接运行此文件时进行单元测试
    # 但不应调用主应用程序的逻辑
    print("PyMuPDF.py 脚本作为模块使用。")
    print("要进行独立测试，请在此处编写或调用测试函数。")
    # 例如:
    # def _test_script():
    #     from dotenv import load_dotenv
    #     load_dotenv()
    #     # ... setup minio client ...
    #     # ... call process_pdf_with_marker ...
    # _test_script()
