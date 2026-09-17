-- Повторное выполнение безопасно. Вызывается в транзакции init_tables().
ALTER TABLE users ADD COLUMN IF NOT EXISTS vk_id BIGINT;
CREATE UNIQUE INDEX IF NOT EXISTS users_vk_id_key ON users (vk_id);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS vk_id BIGINT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS vk_id BIGINT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS vk_file_id TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS vk_media_type TEXT;
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS media_type TEXT;

-- Старый код обозначал VK-пользователей отрицательными Telegram ID.
-- Не перезаписываем противоречащие друг другу идентификаторы.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM users WHERE telegram_id < 0 AND vk_id IS NOT NULL AND vk_id <> -telegram_id)
       OR EXISTS (SELECT 1 FROM orders WHERE user_id < 0 AND vk_id IS NOT NULL AND vk_id <> -user_id)
       OR EXISTS (SELECT 1 FROM reviews WHERE user_id < 0 AND vk_id IS NOT NULL AND vk_id <> -user_id) THEN
        RAISE EXCEPTION 'Conflicting legacy VK identities; migration cancelled';
    END IF;
END $$;

UPDATE users SET vk_id = -telegram_id, telegram_id = NULL WHERE telegram_id < 0;
UPDATE reviews SET vk_id = -user_id, user_id = NULL WHERE user_id < 0;
UPDATE orders SET vk_id = -user_id, user_id = NULL WHERE user_id < 0;

-- VK-вложения старых заказов раньше находились в общем поле media.
UPDATE orders
SET vk_file_id = media,
    vk_media_type = CASE WHEN media LIKE 'photo%' THEN 'photo' ELSE 'video' END,
    media = NULL
WHERE vk_id IS NOT NULL AND user_id IS NULL AND vk_file_id IS NULL
  AND media ~ '^(photo|video)-?[0-9]+_[0-9]+(_[A-Za-z0-9]+)?$';
