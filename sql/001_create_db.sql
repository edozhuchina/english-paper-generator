-- 小学英语出卷系统 建库脚本
-- 使用方式：打开 MySQL Workbench，用有权限的账号连接后执行本文件。
-- 本脚本可重复执行（已做 IF NOT EXISTS 处理）。

CREATE DATABASE IF NOT EXISTS english_exam
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

-- 可选：创建专用账号，避免 root 密码出现在项目配置里。
-- 把 <强密码> 换成你自己的密码，之后在 .env 里填 MYSQL_USER=exam_user / MYSQL_PASSWORD=<强密码>
-- CREATE USER IF NOT EXISTS 'exam_user'@'127.0.0.1' IDENTIFIED BY '<强密码>';
-- GRANT ALL PRIVILEGES ON english_exam.* TO 'exam_user'@'127.0.0.1';
-- FLUSH PRIVILEGES;
