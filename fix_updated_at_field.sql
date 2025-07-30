-- 为node表添加updated_at字段
ALTER TABLE "node" ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- 为现有记录设置updated_at值
UPDATE "node" SET updated_at = created_at WHERE updated_at IS NULL;

-- 为workflow表也添加updated_at字段（如果还没有的话）
ALTER TABLE "workflow" ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
UPDATE "workflow" SET updated_at = created_at WHERE updated_at IS NULL;

-- 为其他可能需要的表添加updated_at字段
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
UPDATE "user" SET updated_at = created_at WHERE updated_at IS NULL;

ALTER TABLE "agent" ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();  
UPDATE "agent" SET updated_at = created_at WHERE updated_at IS NULL;

ALTER TABLE "processor" ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
UPDATE "processor" SET updated_at = created_at WHERE updated_at IS NULL;