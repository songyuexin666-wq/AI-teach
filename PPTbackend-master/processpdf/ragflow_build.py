from ragflow_sdk import RAGFlow
import os, time, datetime


def create_ragflow_resources_from_markdown(markdown_text, base_name, api_key, base_url="http://localhost:8080", uploaded_images=None):
    """
    上传Markdown文本和关联图片信息到RAGFlow，创建知识库和助手
    
    参数:
    - markdown_text: 预处理生成的Markdown文本
    - base_name: 用于命名资源的基础名称 (e.g., from the original PDF)
    - api_key: RAGFlow API密钥
    - base_url: RAGFlow基础URL
    - uploaded_images: 上传的图片信息列表 (用于验证)
    """
    print(f"从Markdown创建RAGFlow资源，基础名称: {base_name}")
    if uploaded_images:
        print(f"Markdown关联了 {len(uploaded_images)} 张已上传到MinIO的图片")
    
    try:
        # 初始化RAGFlow客户端
        rag_object = RAGFlow(api_key=api_key, base_url=base_url)
        
        # 生成时间戳
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 创建唯一的数据集名称
        dataset_name = f"{base_name}_marker_知识库_{timestamp}"
        
        print(f"创建数据集: {dataset_name}")
        # 对于Markdown, 'naive' 或 'semantic_split' 是不错的选择
        dataset = rag_object.create_dataset(
            name=dataset_name,
            description=f"数据集基于 {base_name}.pdf 使用marker生成",
            embedding_model="BAAI/bge-large-zh-v1.5@BAAI"
        )

        print(f"更新数据集 '{dataset_name}' 的PDF处理配置")
        try:
            dataset.update({
                "parser_config": {
                    # "delimiter": "=== 维修案例",
                    "chunk_token_num": 1200,
                    "html4excel": False,
                    "layout_recognize": "DeepDOC",
                    "raptor": {"use_raptor": False}
                }
            })
            print("数据集配置更新成功")
            # print(f"  - 分隔符: '=== 维修案例' (确保每个维修案例独立分块)")
            print(f"  - 分块大小: 1200 tokens (适合完整维修案例)")
            print(f"  - 布局识别: DeepDOC (更好地识别图片和文本)")
        except Exception as update_e:
            print(f"更新数据集解析器配置时出错: {str(update_e)}")
            print("将使用默认分块配置。")
        
        # 上传Markdown文件
        markdown_filename = f"{base_name}_marker.md"
        print(f"上传Markdown内容为文件: {markdown_filename}")
        markdown_bytes = markdown_text.encode('utf-8')
        
        dataset.upload_documents([{
            "display_name": markdown_filename,
            "blob": markdown_bytes
        }])
        
        print(f"Markdown文档上传成功，正在解析...")
        
        # 获取文档ID并开始解析
        docs = dataset.list_documents()
        doc_ids = [doc.id for doc in docs]
        print(f"开始解析文档，ID: {doc_ids}")
        dataset.async_parse_documents(doc_ids)
        
        # 等待文档解析完成
        all_done = False
        max_wait_time = 900  # 最长等待15分钟
        start_time = time.time()
        
        while not all_done and (time.time() - start_time) < max_wait_time:
            all_done = True
            for doc_id in doc_ids:
                docs_check = dataset.list_documents(id=doc_id)
                if docs_check and len(docs_check) > 0:
                    doc_status = docs_check[0].run
                    print(f"文档 {doc_id} 状态: {doc_status}")
                    if doc_status not in ["DONE"]:
                        all_done = False
                        break
                else:
                    print(f"无法获取文档 {doc_id} 的状态")
                    all_done = False
                    break
            
            if not all_done:
                print("文档仍在解析中，等待10秒...")
                time.sleep(10)
        
        if all_done:
            print("文档解析完成！")
            total_chunks = 0
            for doc_id in doc_ids:
                docs_check = dataset.list_documents(id=doc_id)
                if docs_check and len(docs_check) > 0:
                    chunk_count = docs_check[0].chunk_count
                    total_chunks += chunk_count
                    print(f"文档 {doc_id} 解析出 {chunk_count} 个分块")
            if total_chunks == 0:
                print("警告：文档解析完成但没有生成分块，可能解析失败")
                return dataset, None
        else:
            print(f"等待超时（{max_wait_time}秒），部分文档可能仍在解析中")
            success_count = 0
            for doc_id in doc_ids:
                docs_check = dataset.list_documents(id=doc_id)
                if docs_check and len(docs_check) > 0 and docs_check[0].run == "DONE":
                    success_count += 1
            if success_count == 0:
                print("没有文档解析成功，无法创建助手")
                return dataset, None
            else:
                print(f"有 {success_count}/{len(doc_ids)} 个文档解析成功，继续创建助手")

        # 创建唯一的助手名称
        assistant_name = f"{base_name}_marker_助手_{timestamp}"
        print(f"创建聊天助手: {assistant_name}")
        
        # 创建聊天助手
        assistant = rag_object.create_chat(
            name=assistant_name,
            dataset_ids=[dataset.id]
        )
        
        # 更新助手的提示词
        prompt_template = f"""
        请参考以下内容回答用户问题。
        内容源自使用marker工具处理的文档，其中可能包含指向外部存储的图片链接。请结合文本和图片信息，提供全面准确的回答。
        """
        assistant.update({
            "prompt": {
                "prompt": prompt_template,
                "show_quote": True,
                "top_n": 8
            }
        })
        
        print(f"聊天助手 '{assistant_name}' 创建并配置完成。")
        return dataset, assistant
    
    except Exception as e:
        print(f"从Markdown创建RAGFlow资源时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
