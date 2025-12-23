"""
测试 Parquet 数据格式
验证 messages 字段是否正确保存为 JSON 字符串
"""

import json
from datasets import load_dataset


def test_parquet_format(parquet_path: str):
    """
    测试 Parquet 文件格式

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

        print("第一个样本（原始格式）:")
        print(f"messages (type: {type(sample['messages'])}): {sample['messages'][:200]}...")
        print(f"images (type: {type(sample['images'])}): {len(sample['images'])} 个图片")
        print(f"videos (type: {type(sample['videos'])}): {len(sample['videos'])} 个视频")
        print(f"source_file: {sample['source_file']}")
        print(f"media_type: {sample['media_type']}")
        print("\n" + "="*80)

        # 反序列化 messages
        print("反序列化 messages 字段:")
        messages = json.loads(sample['messages'])
        print(f"messages (type: {type(messages)}): ")
        for msg in messages:
            print(f"  - role: {msg['role']}")
            print(f"    content: {msg['content'][:100]}...")
        print("\n" + "="*80)

        # 验证格式
        print("格式验证:")
        assert isinstance(sample['messages'], str), "messages 应该是字符串"
        assert isinstance(messages, list), "反序列化后 messages 应该是列表"
        assert all(isinstance(msg, dict) for msg in messages), "messages 列表中应该全是字典"
        assert all('role' in msg and 'content' in msg for msg in messages), "每个 message 应该有 role 和 content"

        print("✅ 格式验证通过！")
        print(f"✅ messages 字段正确保存为 JSON 字符串")
        print(f"✅ 反序列化后得到标准的 chat template 格式：")
        print(f"   [{{\"role\": \"user\", \"content\": \"...\"}}, {{\"role\": \"assistant\", \"content\": \"...\"}}]")


def show_training_usage():
    """显示训练时如何使用数据"""
    print("\n" + "="*80)
    print("MS-SWIFT 训练时的使用方法:")
    print("="*80)

    code = '''
# 1. 加载数据集
from datasets import load_dataset
import json

dataset = load_dataset("parquet", data_files="/app/data/project_001_converted/*.parquet", split="train")

# 2. 数据预处理（反序列化 messages）
def preprocess(sample):
    """反序列化 messages 字段"""
    sample['messages'] = json.loads(sample['messages'])
    return sample

dataset = dataset.map(preprocess)

# 3. 现在 dataset 中的数据格式为标准的 chat template 格式
print(dataset[0]['messages'])
# 输出: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

# 4. 可以直接用于 MS-SWIFT 训练
# swift sft --dataset /app/data/project_001_converted/ --model Qwen/Qwen2.5-7B-Instruct ...
'''
    print(code)


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
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
