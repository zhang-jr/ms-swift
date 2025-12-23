"""
测试 Parquet 数据格式
验证 MS-SWIFT query-response 格式和 Data URL 格式
"""

import json
from datasets import load_dataset


def test_parquet_format(parquet_path: str):
    """
    测试 Parquet 文件格式（MS-SWIFT 标准格式）

    Args:
        parquet_path: Parquet 文件路径（可以是单个文件或目录）
    """
    print(f"加载数据集: {parquet_path}")

    # 加载数据集
    dataset = load_dataset("parquet", data_files=parquet_path, split="train")

    print(f"数据集大小: {len(dataset)}")
    print(f"数据集列: {dataset.column_names}")
    print("\n" + "="*80)

    # 查看第一个样本
    if len(dataset) > 0:
        sample = dataset[0]

        print("第一个样本（MS-SWIFT 格式）:")
        print(f"query (type: {type(sample['query'])}): {sample['query'][:200]}...")
        print(f"response (type: {type(sample['response'])}): {sample['response'][:200]}...")
        print(f"system (type: {type(sample['system'])}): {sample['system']}")
        print(f"history (type: {type(sample['history'])}): {sample['history']}")
        print(f"images (type: {type(sample['images'])}): {len(sample['images'])} 个图片")
        if len(sample['images']) > 0:
            print(f"  第一个图片格式: {sample['images'][0][:50]}...")
        print(f"videos (type: {type(sample['videos'])}): {len(sample['videos'])} 个视频")
        if len(sample['videos']) > 0:
            print(f"  第一个视频: {sample['videos'][0]}")
        print(f"source_file: {sample['source_file']}")
        print(f"media_type: {sample['media_type']}")
        print("\n" + "="*80)

        # 验证格式
        print("格式验证:")
        assert isinstance(sample['query'], str), "query 应该是字符串"
        assert isinstance(sample['response'], str), "response 应该是字符串"
        assert isinstance(sample['system'], str), "system 应该是字符串"
        assert isinstance(sample['history'], list), "history 应该是列表"
        assert isinstance(sample['images'], list), "images 应该是列表"
        assert isinstance(sample['videos'], list), "videos 应该是列表"

        # 验证 Data URL 格式（如果有图片）
        if len(sample['images']) > 0:
            img = sample['images'][0]
            assert img.startswith('data:image/'), f"图片应该是 Data URL 格式（data:image/...）"
            assert ';base64,' in img, "Data URL 应该包含 ;base64,"
            print(f"✅ 图片格式正确: Data URL (data:image/{{ext}};base64,{{base64}})")

        # 验证 history 格式（嵌套列表）
        if len(sample['history']) > 0:
            assert isinstance(sample['history'][0], list), "history 中的每个元素应该是列表"
            assert len(sample['history'][0]) == 2, "history 中的每个对话应该是 [query, response]"

        print("✅ 格式验证通过！")
        print(f"✅ 使用 MS-SWIFT 原生支持的 query-response 格式")
        print(f"✅ 无需 json.loads() 反序列化，可以直接用于训练")


def show_training_usage():
    """显示训练时如何使用数据"""
    print("\n" + "="*80)
    print("MS-SWIFT 训练时的使用方法:")
    print("="*80)

    code = '''
# 1. 加载数据集（直接使用，无需额外处理）
from datasets import load_dataset

dataset = load_dataset("parquet", data_files="/app/data/project_001_converted/*.parquet", split="train")

# 2. 数据已经是标准的 MS-SWIFT 格式，可以直接使用
print(dataset[0])
# 输出示例:
# {
#     "query": "<image>图片中有什么异常",
#     "response": "检测到以下异常...",
#     "system": "",
#     "history": [],
#     "images": ["data:image/jpeg;base64,/9j/4AAQ..."],
#     "videos": []
# }

# 3. 直接用于 MS-SWIFT 训练（无需任何预处理）
# swift sft \\
#     --dataset /app/data/project_001_converted/ \\
#     --model Qwen/Qwen2.5-7B-Instruct \\
#     --train_type lora \\
#     --num_train_epochs 1

# 注：MS-SWIFT 原生支持以下格式:
# {"system": "<system>", "query": "<query>", "response": "<response>", "history": [["<q1>", "<r1>"]]}
# 我们的数据完全符合这个格式，可以直接使用！
'''
    print(code)


def show_data_format_examples():
    """显示不同类型数据的格式示例"""
    print("\n" + "="*80)
    print("数据格式示例:")
    print("="*80)

    examples = {
        "单张图片": {
            "query": "<image>图片中有什么异常",
            "response": "检测到以下异常：...",
            "system": "",
            "history": [],
            "images": ["data:image/jpeg;base64,{base64_encoded}"],
            "videos": []
        },
        "多张图片（PDF）": {
            "query": "<image><image><image>文档中哪些页面有问题",
            "response": "第2页存在异常：...",
            "system": "",
            "history": [],
            "images": [
                "data:image/png;base64,{page1_base64}",
                "data:image/png;base64,{page2_base64}",
                "data:image/png;base64,{page3_base64}"
            ],
            "videos": []
        },
        "视频": {
            "query": "<video>视频中哪些帧有问题",
            "response": "第5秒处检测到异常：...",
            "system": "",
            "history": [],
            "images": [],
            "videos": ["/app/data/project_001/uploads/video.mp4"]
        },
        "多轮对话": {
            "query": "继续分析",
            "response": "根据上次的分析结果，我发现...",
            "system": "你是一个专业的文档分析助手",
            "history": [
                ["第一个问题", "第一个回答"],
                ["第二个问题", "第二个回答"]
            ],
            "images": [],
            "videos": []
        }
    }

    for name, example in examples.items():
        print(f"\n{name}:")
        print(json.dumps(example, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python test_parquet_format.py <parquet_path>")
        print("示例: python test_parquet_format.py /app/data/project_001_converted/train-00000-of-00001.parquet")
        sys.exit(1)

    parquet_path = sys.argv[1]

    try:
        test_parquet_format(parquet_path)
        show_training_usage()
        show_data_format_examples()
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
