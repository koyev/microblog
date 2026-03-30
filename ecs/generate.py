#!/usr/bin/env python3
"""Generate ECS task definition JSON files from environment variables.

Required env vars:
    ACCOUNT_ID, REGION, RDS_ENDPOINT, DB_PASSWORD, RABBITMQ_URL
"""
import json
import os

ACCOUNT_ID = os.environ["ACCOUNT_ID"]
REGION = os.environ["REGION"]
RDS_ENDPOINT = os.environ["RDS_ENDPOINT"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
RABBITMQ_URL = os.environ["RABBITMQ_URL"]

EXECUTION_ROLE = f"arn:aws:iam::{ACCOUNT_ID}:role/ecsTaskExecutionRole"
TASK_ROLE = f"arn:aws:iam::{ACCOUNT_ID}:role/ecsTaskRole"


def task_def(family, container_name, port, env_vars):
    return {
        "family": family,
        "networkMode": "awsvpc",
        "requiresCompatibilities": ["FARGATE"],
        "cpu": "256",
        "memory": "512",
        "executionRoleArn": EXECUTION_ROLE,
        "taskRoleArn": TASK_ROLE,
        "containerDefinitions": [
            {
                "name": container_name,
                "image": "IMAGE_PLACEHOLDER",
                "essential": True,
                "portMappings": [
                    {
                        "name": container_name,
                        "containerPort": port,
                        "protocol": "tcp",
                        "appProtocol": "http",
                    }
                ],
                "environment": [
                    {"name": k, "value": v} for k, v in env_vars.items()
                ],
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": f"/ecs/microblog-{container_name}",
                        "awslogs-region": REGION,
                        "awslogs-stream-prefix": "ecs",
                        "awslogs-create-group": "true",
                    },
                },
            },
        ],
    }


SERVICES = {
    "api-gateway": (
        "api-gateway",
        8080,
        {
            "USER_SERVICE_HOST": "user-service",
            "POST_SERVICE_HOST": "post-service",
            "COMMENT_SERVICE_HOST": "comment-service",
            "NOTIFICATION_SERVICE_HOST": "notification-service",
        },
    ),
    "user-service": (
        "user-service",
        8001,
        {
            "DATABASE_URL": f"postgresql://postgres:{DB_PASSWORD}@{RDS_ENDPOINT}:5432/userdb?sslmode=require",
        },
    ),
    "post-service": (
        "post-service",
        8002,
        {
            "DATABASE_URL": f"postgresql://postgres:{DB_PASSWORD}@{RDS_ENDPOINT}:5432/postdb?sslmode=require",
            "RABBITMQ_URL": RABBITMQ_URL,
        },
    ),
    "comment-service": (
        "comment-service",
        8003,
        {
            "DATABASE_URL": f"postgresql://postgres:{DB_PASSWORD}@{RDS_ENDPOINT}:5432/commentdb?sslmode=require",
        },
    ),
    "notification-service": (
        "notification-service",
        8004,
        {
            "DATABASE_URL": f"postgresql://postgres:{DB_PASSWORD}@{RDS_ENDPOINT}:5432/notificationdb?sslmode=require",
            "RABBITMQ_URL": RABBITMQ_URL,
        },
    ),
}

os.makedirs("ecs", exist_ok=True)
for svc_name, (container_name, port, env_vars) in SERVICES.items():
    td = task_def(f"microblog-{svc_name}", container_name, port, env_vars)
    with open(f"ecs/{svc_name}.json", "w") as f:
        json.dump(td, f, indent=2)
    print(f"Generated ecs/{svc_name}.json")
