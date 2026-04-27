#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import json
import sys
import io 
from dotenv import load_dotenv
from processpdf.PyMuPDF import process_pdf_with_marker
from ragflow_build import create_ragflow_resources_from_markdown
from minio import Minio
from minio.error import S3Error

def main():
    # 从 .env 文件加载环境变量
    load_dotenv()

    # --- 参数解析器设置 ---
    parser = argparse.ArgumentParser(description='使用 marker 处理PDF，提取Markdown和图片，上传图片到MinIO，并创建RAGFlow资源')
    parser.add_argument('pdf_path', help='PDF文件路径')
    parser.add_argument('--skip_ragflow', action='store_true', help='跳过创建RAGFlow知识库，只处理图片和映射上传')

    args = parser.parse_args()

    # --- 从环境变量加载配置 ---
    ragflow_api_key = os.getenv("RAGFLOW_API_KEY")
    ragflow_base_url = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")
    minio_endpoint = os.getenv("MINIO_ENDPOINT")
    minio_access_key = os.getenv("MINIO_ACCESS_KEY")
    minio_secret_key = os.getenv("MINIO_SECRET_KEY")
    minio_bucket_name = os.getenv("MINIO_BUCKET_NAME")
    minio_secure_str = os.getenv("MINIO_SECURE", "false")
    minio_secure = minio_secure_str.lower() == "true"

    # --- 清理环境变量字符串 ---
    if minio_endpoint:
        minio_endpoint = minio_endpoint.strip()
        comment_index = minio_endpoint.find('#')
        if comment_index != -1:
            minio_endpoint = minio_endpoint[:comment_index].strip()
        if minio_endpoint.startswith('"') and minio_endpoint.endswith('"'):
            minio_endpoint = minio_endpoint[1:-1]
        elif minio_endpoint.startswith("'") and minio_endpoint.endswith("'"):
            minio_endpoint = minio_endpoint[1:-1]

    if minio_access_key:
        minio_access_key = minio_access_key.strip()
        comment_index = minio_access_key.find('#')
        if comment_index != -1:
            minio_access_key = minio_access_key[:comment_index].strip()
        if minio_access_key.startswith('"') and minio_access_key.endswith('"'):
            minio_access_key = minio_access_key[1:-1]
        elif minio_access_key.startswith("'") and minio_access_key.endswith("'"):
            minio_access_key = minio_access_key[1:-1]

    if minio_secret_key:
        minio_secret_key = minio_secret_key.strip()
        comment_index = minio_secret_key.find('#')
        if comment_index != -1:
            minio_secret_key = minio_secret_key[:comment_index].strip()
        if minio_secret_key.startswith('"') and minio_secret_key.endswith('"'):
            minio_secret_key = minio_secret_key[1:-1]
        elif minio_secret_key.startswith("'") and minio_secret_key.endswith("'"):
            minio_secret_key = minio_secret_key[1:-1]

    if minio_bucket_name:
        minio_bucket_name = minio_bucket_name.strip()
        comment_index = minio_bucket_name.find('#')
        if comment_index != -1:
            minio_bucket_name = minio_bucket_name[:comment_index].strip()
        if minio_bucket_name.startswith('"') and minio_bucket_name.endswith('"'):
            minio_bucket_name = minio_bucket_name[1:-1]
        elif minio_bucket_name.startswith("'") and minio_bucket_name.endswith("'"):
            minio_bucket_name = minio_bucket_name[1:-1]

    # 定义 Minio 路径
    minio_map_prefix = "mappings/"
    minio_image_prefix = "images/"

    # --- 验证必要配置 ---
    required_vars = {
        "RAGFLOW_API_KEY": ragflow_api_key,
        "MINIO_ENDPOINT": minio_endpoint,
        "MINIO_ACCESS_KEY": minio_access_key,
        "MINIO_SECRET_KEY": minio_secret_key,
        "MINIO_BUCKET_NAME": minio_bucket_name
    }
    missing_vars = [name for name, value in required_vars.items() if not value]
    if missing_vars:
        print(f"错误：以下必要的环境变量未在 .env 文件中设置或为空: {', '.join(missing_vars)}")
        sys.exit(1)

    # --- 初始化 MinIO 客户端 ---
    minio_client = None
    try:
        print(f"正在连接 MinIO: {minio_endpoint} ...")
        minio_client = Minio(
            minio_endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            secure=minio_secure
        )
        found = minio_client.bucket_exists(minio_bucket_name)
        if not found:
            print(f"错误：MinIO Bucket '{minio_bucket_name}' 不存在或无法访问。")
            sys.exit(1)
        else:
             print(f"MinIO Bucket '{minio_bucket_name}' 连接成功。")
    except Exception as exc:
        print(f"错误：连接或初始化 MinIO 失败: {exc}")
        sys.exit(1)


    # --- 初始化变量 ---
    markdown_text = None
    markdown_filename = None
    map_public_url = None

    try:
        # --- 第1步: 使用 marker 处理PDF，提取Markdown并上传图片到 MinIO ---
        print(f"第1步：使用 marker 处理PDF，提取Markdown并上传图片到 MinIO...")
        minio_endpoint_for_url=f"{'https://' if minio_secure else 'http://'}{minio_endpoint}"

        markdown_text, uploaded_images = process_pdf_with_marker(
            args.pdf_path,
            minio_client=minio_client,
            bucket_name=minio_bucket_name,
            image_prefix=minio_image_prefix,
            minio_endpoint_for_url=minio_endpoint_for_url
        )
        print(f"Marker 处理完成，生成Markdown，上传了 {len(uploaded_images)} 张图片。")


        # --- 第2步: 将Markdown文本保存到本地 ---
        base_pdf_name = os.path.splitext(os.path.basename(args.pdf_path))[0]
        markdown_filename = f"{base_pdf_name}_marker.md"
        with open(markdown_filename, "w", encoding="utf-8") as f:
            f.write(markdown_text)
        print(f"第2步：Markdown文档已保存到本地文件 {markdown_filename}")

        # --- 第3步: 上传图片URL映射到MinIO ---
        image_url_map = {img['new_filename']: img['url'] for img in uploaded_images}
        if image_url_map:
            map_object_name = f"{minio_map_prefix.strip('/')}/{base_pdf_name}_marker_image_map.json"
            map_json_string = json.dumps(image_url_map, ensure_ascii=False, indent=4)
            map_bytes = map_json_string.encode('utf-8')
            map_size = len(map_bytes)

            print(f"第3步：准备上传图片URL映射到 MinIO Object: {minio_bucket_name}/{map_object_name} ...")
            try:
                result = minio_client.put_object(
                    minio_bucket_name,
                    map_object_name,
                    io.BytesIO(map_bytes),
                    length=map_size,
                    content_type='application/json',
                )
                print(f"第3步：图片URL映射成功上传到 MinIO。 ETag: {result.etag}")
                map_public_url = f"{minio_endpoint_for_url}/{minio_bucket_name}/{map_object_name}"
                print(f"  - 映射文件公开访问URL: {map_public_url}")

            except S3Error as exc:
                print(f"错误：上传映射到 MinIO 失败: {exc}")
                raise
        else:
            print("第3步：未生成图片URL映射，跳过上传到 MinIO。")

        # --- 第4步: 处理 --skip_ragflow ---
        if args.skip_ragflow:
            print("已跳过创建RAGFlow知识库。")
            print("\n处理完成！")
            if markdown_filename: print(f"- Markdown文档已保存到本地: {markdown_filename}")
            if map_public_url: print(f"- 图片URL映射已上传到 MinIO: {map_public_url}")
            print("\n后续步骤：")
            print(f"1. 手动将生成的 {markdown_filename} 文件上传到 RAGFlow 知识库。")
            print(f"2. RAGFlow 将自动识别 Markdown 中的图片链接。")
            return

        # --- 第5步: 创建 RAGFlow 资源 ---
        if not ragflow_api_key:
            print("错误：RAGFLOW_API_KEY 未在 .env 文件中设置。")
            return

        print(f"第4步：从Markdown创建RAGFlow知识库和助手 (Base URL: {ragflow_base_url})...")
        dataset, assistant = create_ragflow_resources_from_markdown(
            markdown_text=markdown_text,
            base_name=base_pdf_name,
            api_key=ragflow_api_key,
            base_url=ragflow_base_url,
            uploaded_images=uploaded_images
        )

        # --- 最终打印信息 ---
        print(f"\n处理完成！")
        if markdown_filename: print(f"- Markdown文档已保存到本地: {markdown_filename}")
        if map_public_url: print(f"- 图片URL映射已上传到 MinIO: {map_public_url}")
        if dataset: print(f"- 知识库ID: {dataset.id}")
        if assistant: print(f"- 聊天助手ID: {assistant.id}")
        print("\n说明：")
        print("- Markdown中的图片链接指向公网可访问的MinIO地址")
        print("- RAGFlow 将下载这些图片并存储在其内部")


    except Exception as e:
        print(f"处理过程中出现错误：{str(e)}")
        import traceback
        traceback.print_exc()
        if markdown_text and markdown_filename:
            try:
                with open(markdown_filename, "w", encoding="utf-8") as f: f.write(markdown_text)
                print(f"(错误后) Markdown文档已保存到{markdown_filename}")
            except Exception as write_err: print(f"(错误后) 保存Markdown文档失败: {write_err}")

if __name__ == "__main__":
    main() 