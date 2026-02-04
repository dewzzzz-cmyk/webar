#!/usr/bin/env python3
"""
MinIO Initialization Script
Создает необходимые buckets для системы обучения PPE Detection

Использование:
    python init_minio.py
    
Или в Docker:
    docker exec ppe_api python /app/scripts/init_minio.py
"""

import os
import sys
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('minio_init')

try:
    from minio import Minio
    from minio.error import S3Error
except ImportError:
    logger.error("minio package not installed. Run: pip install minio")
    sys.exit(1)


def wait_for_minio(client: Minio, max_retries: int = 30, delay: int = 2) -> bool:
    """Wait for MinIO to become available."""
    for attempt in range(max_retries):
        try:
            client.list_buckets()
            logger.info("MinIO is available")
            return True
        except Exception as e:
            logger.warning(f"Waiting for MinIO... ({attempt + 1}/{max_retries})")
            time.sleep(delay)
    return False


def init_minio():
    """Initialize MinIO with required buckets."""
    
    # Configuration from environment
    endpoint = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
    access_key = os.getenv('MINIO_ACCESS_KEY', os.getenv('MINIO_ROOT_USER', 'minioadmin'))
    secret_key = os.getenv('MINIO_SECRET_KEY', os.getenv('MINIO_ROOT_PASSWORD', 'minioadmin123'))
    secure = os.getenv('MINIO_SECURE', 'false').lower() == 'true'
    
    logger.info(f"Connecting to MinIO at {endpoint}")
    
    # Create client
    client = Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure
    )
    
    # Wait for MinIO to be ready
    if not wait_for_minio(client):
        logger.error("MinIO is not available after timeout")
        sys.exit(1)
    
    # Required buckets
    buckets = [
        {
            'name': 'training-images',
            'description': 'Training images for model training'
        },
        {
            'name': 'training-models',
            'description': 'Trained model files'
        },
        {
            'name': 'violations',
            'description': 'Violation images from detection'
        },
    ]
    
    # Create buckets
    for bucket_info in buckets:
        bucket_name = bucket_info['name']
        try:
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
                logger.info(f"✅ Created bucket: {bucket_name}")
            else:
                logger.info(f"✓ Bucket exists: {bucket_name}")
        except S3Error as e:
            logger.error(f"❌ Failed to create bucket {bucket_name}: {e}")
            continue
        
        # Set bucket policy for anonymous read (optional, uncomment if needed)
        # policy = {
        #     "Version": "2012-10-17",
        #     "Statement": [
        #         {
        #             "Effect": "Allow",
        #             "Principal": {"AWS": "*"},
        #             "Action": ["s3:GetObject"],
        #             "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
        #         }
        #     ]
        # }
        # import json
        # client.set_bucket_policy(bucket_name, json.dumps(policy))
    
    logger.info("="*50)
    logger.info("MinIO initialization complete!")
    logger.info("="*50)
    
    # List all buckets
    logger.info("Available buckets:")
    for bucket in client.list_buckets():
        logger.info(f"  - {bucket.name} (created: {bucket.creation_date})")


if __name__ == '__main__':
    init_minio()
