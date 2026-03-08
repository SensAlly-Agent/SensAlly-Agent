"""
FSRS + PostgreSQL 英语学习系统演示代码
演示如何使用 py-fsrs 配合 PostgreSQL 数据库管理单词学习进度

使用说明：
1. 安装依赖：pip install psycopg psycopg-pool fsrs
2. 运行：python fsrs_postgresql_demo.py
   （默认使用项目现有的 langgraph_test 数据库）

3. 如需使用其他数据库，设置环境变量：
   export DB_URI="postgresql://user:password@localhost:5432/other_database"

注意：
- 本系统会在数据库中创建 fsrs_* 开头的表，与现有表不冲突
- 默认连接到 langgraph_test 数据库（项目 Agent 使用的数据库）
- 所有 FSRS 表都有 fsrs_ 前缀，便于识别和管理
"""

import os
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# PostgreSQL 相关导入
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# FSRS 相关导入
from fsrs import Scheduler, Card, Rating, ReviewLog, State


class FSRSPostgreSQLSystem:
    """使用 FSRS 算法和 PostgreSQL 数据库的学习系统"""

    def __init__(self, db_uri: Optional[str] = None, schema: str = "public"):
        """
        初始化学习系统

        参数:
            db_uri: PostgreSQL 连接字符串，如 "postgresql://user:password@localhost:5432/dbname"
                   如果不提供，会尝试从环境变量 DB_URI 读取
                   如果环境变量也没有，默认使用 "postgresql://localhost/langgraph_test"
            schema: 数据库 schema，默认为 "public"
        """
        # 获取数据库连接字符串
        # 优先级：参数 > 环境变量 > 默认值（langgraph_test）
        self.db_uri = db_uri or os.getenv("DB_URI") or "postgresql://localhost/langgraph_test"

        print(f"📊 连接到数据库: {self.db_uri.split('@')[-1] if '@' in self.db_uri else self.db_uri.split('/')[-1]}")

        self.schema = schema

        # 创建连接池
        self.pool = ConnectionPool(
            self.db_uri,
            min_size=2,
            max_size=10,
            kwargs={
                "autocommit": False,  # 我们自己管理事务
                "row_factory": dict_row,  # 返回字典格式的行
            },
            open=True,  # 显式指定打开连接池
        )

        # 等待连接池初始化完成
        self.pool.wait()

        # 初始化 FSRS 调度器
        self.scheduler = Scheduler(
            maximum_interval=180,  # 最大复习间隔 180 天（半年）
            # 其他参数使用系统默认值：
            # - desired_retention=0.9 (90% 记忆保持率)
            # - learning_steps=(1分钟, 10分钟)
            # - relearning_steps=(10分钟)
            # - enable_fuzzing=True
        )

        # 创建数据库表
        self._create_tables()

    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        with self.pool.connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _create_tables(self):
        """创建必要的数据库表"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # ========== 全局表（静态内容，所有用户共享）==========

                # 全局单词表 - 存储单词静态内容
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.global_words (
                        word TEXT PRIMARY KEY,
                        translation TEXT,
                        phonetic TEXT,
                        usphone TEXT,
                        ukphone TEXT,
                        definition TEXT,
                        ted_videos JSONB,
                        exchange TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # 全局单词书映射表 - 存储单词与单词书的映射（全局）
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.global_word_books (
                        id BIGSERIAL PRIMARY KEY,
                        word TEXT NOT NULL,
                        book_name TEXT NOT NULL,
                        UNIQUE(word, book_name),
                        FOREIGN KEY (word) REFERENCES {self.schema}.global_words (word)
                    )
                """)

                # 全局表索引
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_global_word_books_book
                    ON {self.schema}.global_word_books (book_name)
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_global_word_books_word
                    ON {self.schema}.global_word_books (word)
                """)

                # ========== 用户表（用户特定数据）==========

                # 单词表 - 存储单词基本信息
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.fsrs_words (
                        word_id BIGSERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        word TEXT NOT NULL,
                        translation TEXT,
                        phonetic TEXT,
                        example TEXT,
                        difficulty_level TEXT,
                        usphone TEXT,
                        ukphone TEXT,
                        definition TEXT,
                        ted_videos JSONB,
                        ai_explanation TEXT,
                        scene_content TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(word, user_id),
                        UNIQUE(word_id, user_id)
                    )
                """)

                # 卡片表 - 存储 FSRS 卡片数据
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.fsrs_cards (
                        card_id BIGINT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        word_id BIGINT NOT NULL,
                        state INTEGER NOT NULL,
                        step INTEGER,
                        stability DOUBLE PRECISION,
                        difficulty DOUBLE PRECISION,
                        due TIMESTAMP WITH TIME ZONE NOT NULL,
                        last_review TIMESTAMP WITH TIME ZONE,
                        card_data JSONB NOT NULL,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(word_id, user_id),
                        UNIQUE(card_id, user_id),
                        FOREIGN KEY (word_id, user_id)
                            REFERENCES {self.schema}.fsrs_words (word_id, user_id) ON DELETE CASCADE
                    )
                """)

                # 复习记录表 - 存储每次复习的历史
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.fsrs_review_logs (
                        log_id BIGSERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        card_id BIGINT NOT NULL,
                        word_id BIGINT NOT NULL,
                        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 4),
                        review_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
                        review_duration INTEGER,
                        state_before INTEGER,
                        state_after INTEGER,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (card_id, user_id)
                            REFERENCES {self.schema}.fsrs_cards (card_id, user_id) ON DELETE CASCADE,
                        FOREIGN KEY (word_id, user_id)
                            REFERENCES {self.schema}.fsrs_words (word_id, user_id) ON DELETE CASCADE
                    )
                """)

                # 学习统计表 - 存储学习统计信息
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.fsrs_learning_stats (
                        stat_id BIGSERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        date DATE NOT NULL,
                        words_learned INTEGER DEFAULT 0,
                        words_reviewed INTEGER DEFAULT 0,
                        total_time_ms BIGINT DEFAULT 0,
                        average_rating DOUBLE PRECISION,
                        retention_rate DOUBLE PRECISION,
                        UNIQUE(date, user_id)
                    )
                """)

                # 单词书关联表 - 存储单词与单词书的多对多关系
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.fsrs_word_books (
                        id BIGSERIAL PRIMARY KEY,
                        word_id BIGINT NOT NULL,
                        user_id TEXT NOT NULL,
                        book_name TEXT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(word_id, user_id, book_name),
                        FOREIGN KEY (word_id, user_id)
                            REFERENCES {self.schema}.fsrs_words (word_id, user_id) ON DELETE CASCADE
                    )
                """)

                # ========== 创建索引（与第一阶段迁移一致）==========

                # fsrs_words 索引
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_fsrs_words_user_id
                    ON {self.schema}.fsrs_words (user_id)
                """)

                # fsrs_cards 索引
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_fsrs_cards_due
                    ON {self.schema}.fsrs_cards (due)
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_fsrs_cards_word
                    ON {self.schema}.fsrs_cards (word_id)
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_fsrs_cards_user_id
                    ON {self.schema}.fsrs_cards (user_id)
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_fsrs_cards_user_due
                    ON {self.schema}.fsrs_cards (user_id, due)
                """)

                # fsrs_review_logs 索引
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_fsrs_logs_card
                    ON {self.schema}.fsrs_review_logs (card_id)
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_fsrs_logs_datetime
                    ON {self.schema}.fsrs_review_logs (review_datetime)
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_fsrs_review_logs_user_id
                    ON {self.schema}.fsrs_review_logs (user_id)
                """)
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_fsrs_review_logs_user_date
                    ON {self.schema}.fsrs_review_logs (user_id, review_datetime)
                """)

                # fsrs_learning_stats 索引
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_fsrs_learning_stats_user_id
                    ON {self.schema}.fsrs_learning_stats (user_id)
                """)

                # fsrs_word_books 索引
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_fsrs_word_books_user_book
                    ON {self.schema}.fsrs_word_books (user_id, book_name)
                """)

                # ========== 用户设置表 ==========
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.user_settings (
                        user_id TEXT PRIMARY KEY,
                        last_wordbook_name TEXT,
                        last_wordbook_category TEXT,
                        pronunciation TEXT DEFAULT 'us',
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # ========== 用户已加载单词书表 ==========
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.schema}.user_loaded_books (
                        id BIGSERIAL PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        book_name TEXT NOT NULL,
                        category TEXT,
                        loaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, book_name)
                    )
                """)

                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_user_loaded_books_user
                    ON {self.schema}.user_loaded_books (user_id)
                """)

                # ========== 数据迁移（已完成，2026-01-10）==========
                # 已将 difficulty_level 数据迁移到 fsrs_word_books 表（12,791 条）
                # 新用户通过 add_word(book_name=xxx) 直接写入，无需迁移
                # 如需重新迁移，取消下面注释：
                # cur.execute(f"""
                #     INSERT INTO {self.schema}.fsrs_word_books (word_id, user_id, book_name)
                #     SELECT word_id, user_id, difficulty_level
                #     FROM {self.schema}.fsrs_words
                #     WHERE difficulty_level IS NOT NULL
                #       AND difficulty_level != ''
                #     ON CONFLICT (word_id, user_id, book_name) DO NOTHING
                # """)

    def add_word(
        self,
        word: str,
        user_id: str,
        translation: str = None,
        phonetic: str = None,
        example: str = None,
        difficulty_level: str = None,
        usphone: str = None,
        ukphone: str = None,
        definition: str = None,
        ted_videos: list = None,
        book_name: str = None,
    ) -> int:
        """
        添加新单词到系统

        参数:
            word: 单词
            user_id: 用户ID（用于多用户隔离）
            translation: 中文翻译
            phonetic: 音标
            example: 例句
            difficulty_level: 难度等级 (如: 'CET4', 'CET6', 'TOEFL', 'GRE')
            usphone: 美式音标
            ukphone: 英式音标
            definition: 英文定义
            ted_videos: TED视频实例列表
            book_name: 单词书名称（用于多对多关系）

        返回:
            word_id: 单词ID
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 使用 ON CONFLICT 处理重复
                cur.execute(
                    f"""
                    INSERT INTO {self.schema}.fsrs_words
                    (user_id, word, translation, phonetic, example, difficulty_level, usphone, ukphone, definition, ted_videos)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (word, user_id) DO NOTHING
                    RETURNING word_id
                """,
                    (user_id, word, translation, phonetic, example, difficulty_level, usphone, ukphone, definition, json.dumps(ted_videos) if ted_videos else None),
                )

                result = cur.fetchone()
                if result:
                    word_id = result["word_id"]
                    # 为新单词创建卡片
                    self._create_card_for_word(word_id, user_id, conn)
                else:
                    # 单词已存在，获取 word_id
                    cur.execute(
                        f"SELECT word_id FROM {self.schema}.fsrs_words WHERE word = %s AND user_id = %s",
                        (word, user_id),
                    )
                    word_id = cur.fetchone()["word_id"]

                    # 检查是否存在卡片，不存在则补建
                    cur.execute(
                        f"SELECT 1 FROM {self.schema}.fsrs_cards WHERE word_id = %s AND user_id = %s",
                        (word_id, user_id),
                    )
                    if not cur.fetchone():
                        self._create_card_for_word(word_id, user_id, conn)

                # 如果指定了单词书，添加到 fsrs_word_books 表
                if book_name:
                    cur.execute(
                        f"""
                        INSERT INTO {self.schema}.fsrs_word_books (word_id, user_id, book_name)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (word_id, user_id, book_name) DO NOTHING
                    """,
                        (word_id, user_id, book_name),
                    )

                return word_id

    def _create_card_for_word(self, word_id: int, user_id: str, conn) -> None:
        """为单词创建 FSRS 卡片"""
        # 使用 UUID v4 生成全局唯一的 card_id，避免多用户并发时的 ID 冲突
        # 取 63 位确保落在 PostgreSQL BIGINT 有符号范围内 (0 到 2^63-1)
        card_id = uuid.uuid4().int >> 65
        card = Card(card_id=card_id)

        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self.schema}.fsrs_cards
                (card_id, user_id, word_id, state, step, stability, difficulty, due, last_review, card_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (word_id, user_id) DO NOTHING
            """,
                (
                    card.card_id,
                    user_id,
                    word_id,
                    int(card.state),
                    card.step,
                    card.stability,
                    card.difficulty,
                    card.due,
                    card.last_review,
                    json.dumps(card.to_dict()),
                ),
            )

    def add_word_to_book(self, word_id: int, user_id: str, book_name: str) -> bool:
        """
        将单词添加到指定单词书（多对多关系）

        参数:
            word_id: 单词ID
            user_id: 用户ID
            book_name: 单词书名称

        返回:
            bool: 是否成功添加（如果已存在则返回 False）
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.schema}.fsrs_word_books (word_id, user_id, book_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (word_id, user_id, book_name) DO NOTHING
                    RETURNING id
                """,
                    (word_id, user_id, book_name),
                )
                result = cur.fetchone()
                return result is not None

    def review_word(
        self, word: str, rating: int,
        user_id: str,
        review_duration_ms: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        复习单词

        参数:
            word: 要复习的单词
            rating: 评分 (1=Again, 2=Hard, 3=Good, 4=Easy)
            user_id: 用户ID（用于多用户隔离）
            review_duration_ms: 复习耗时（毫秒，可选）

        返回:
            包含复习结果的字典
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 获取单词ID
                cur.execute(
                    f"SELECT word_id FROM {self.schema}.fsrs_words WHERE word = %s AND user_id = %s",
                    (word, user_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"单词 '{word}' 不存在")
                word_id = row["word_id"]

                # 获取卡片数据
                cur.execute(
                    f"""
                    SELECT card_id, card_data, state
                    FROM {self.schema}.fsrs_cards
                    WHERE word_id = %s AND user_id = %s
                """,
                    (word_id, user_id),
                )
                row = cur.fetchone()

                if not row:
                    # 如果没有卡片，创建一个
                    self._create_card_for_word(word_id, user_id, conn)
                    cur.execute(
                        f"""
                        SELECT card_id, card_data, state
                        FROM {self.schema}.fsrs_cards
                        WHERE word_id = %s AND user_id = %s
                    """,
                        (word_id, user_id),
                    )
                    row = cur.fetchone()

                card_id = row["card_id"]
                old_state = row["state"]

                # 从数据库恢复卡片对象
                card = Card.from_dict(row["card_data"])

                # 使用 FSRS 算法进行复习
                rating_enum = Rating(rating)

                # 执行复习（使用默认的当前时间，传递复习耗时）
                new_card, review_log = self.scheduler.review_card(
                    card=card, rating=rating_enum, review_duration=review_duration_ms
                )

                # 更新数据库中的卡片数据
                cur.execute(
                    f"""
                    UPDATE {self.schema}.fsrs_cards
                    SET state = %s, step = %s, stability = %s, difficulty = %s,
                        due = %s, last_review = %s, card_data = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE card_id = %s
                """,
                    (
                        int(new_card.state),
                        new_card.step,
                        new_card.stability,
                        new_card.difficulty,
                        new_card.due,
                        new_card.last_review,
                        json.dumps(new_card.to_dict()),
                        card_id,
                    ),
                )

                # 记录复习日志
                cur.execute(
                    f"""
                    INSERT INTO {self.schema}.fsrs_review_logs
                    (user_id, card_id, word_id, rating, review_datetime, review_duration,
                     state_before, state_after)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        user_id,
                        card_id,
                        word_id,
                        rating,
                        review_log.review_datetime,
                        review_log.review_duration,
                        old_state,
                        int(new_card.state),
                    ),
                )

                # 更新当日统计
                self._update_daily_stats(review_log.review_datetime.date(), rating, user_id, conn)

                # 计算下次复习间隔
                interval_days = (new_card.due - review_log.review_datetime).days

                return {
                    "word": word,
                    "next_review_date": new_card.due.isoformat(),
                    "interval_days": interval_days,
                    "state": new_card.state.name,
                    "difficulty": new_card.difficulty,
                    "stability": new_card.stability,
                    "retrievability": self.scheduler.get_card_retrievability(new_card),
                }

    def get_due_words(
        self, user_id: str, limit: Optional[int] = None, book_name: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取需要复习的单词列表（只返回已经学习过的单词）

        参数:
            user_id: 用户ID
            limit: 返回的最大单词数（None 表示全部）
            book_name: 单词书名称（可选，用于过滤特定单词书的单词）

        返回:
            需要复习的单词信息列表
        """
        now = datetime.now(timezone.utc)

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 构建基础查询
                # 静态内容从 global_words 获取（COALESCE 回退到 fsrs_words 以兼容旧数据）
                # AI 内容从 fsrs_words 获取（用户隔离）
                if book_name:
                    # 如果指定了单词书，JOIN global_word_books 表过滤
                    query = f"""
                        SELECT w.word,
                               COALESCE(g.translation, w.translation) as translation,
                               COALESCE(g.phonetic, w.phonetic) as phonetic,
                               w.example,
                               COALESCE(g.usphone, w.usphone) as usphone,
                               COALESCE(g.ukphone, w.ukphone) as ukphone,
                               COALESCE(g.definition, w.definition) as definition,
                               COALESCE(g.ted_videos, w.ted_videos) as ted_videos,
                               g.exchange,
                               w.ai_explanation, w.scene_content,
                               c.due, c.state, c.stability, c.difficulty, c.card_data
                        FROM {self.schema}.fsrs_cards c
                        JOIN {self.schema}.fsrs_words w ON c.word_id = w.word_id AND c.user_id = w.user_id
                        LEFT JOIN {self.schema}.global_words g ON w.word = g.word
                        JOIN {self.schema}.global_word_books gb ON w.word = gb.word
                        WHERE c.due <= %s AND c.last_review IS NOT NULL AND c.user_id = %s AND gb.book_name = %s
                        ORDER BY c.due ASC
                    """
                    params = (now, user_id, book_name)
                else:
                    # 不过滤，返回所有单词
                    query = f"""
                        SELECT w.word,
                               COALESCE(g.translation, w.translation) as translation,
                               COALESCE(g.phonetic, w.phonetic) as phonetic,
                               w.example,
                               COALESCE(g.usphone, w.usphone) as usphone,
                               COALESCE(g.ukphone, w.ukphone) as ukphone,
                               COALESCE(g.definition, w.definition) as definition,
                               COALESCE(g.ted_videos, w.ted_videos) as ted_videos,
                               g.exchange,
                               w.ai_explanation, w.scene_content,
                               c.due, c.state, c.stability, c.difficulty, c.card_data
                        FROM {self.schema}.fsrs_cards c
                        JOIN {self.schema}.fsrs_words w ON c.word_id = w.word_id AND c.user_id = w.user_id
                        LEFT JOIN {self.schema}.global_words g ON w.word = g.word
                        WHERE c.due <= %s AND c.last_review IS NOT NULL AND c.user_id = %s
                        ORDER BY c.due ASC
                    """
                    params = (now, user_id)

                if limit:
                    query += " LIMIT %s"
                    params = params + (int(limit),)

                cur.execute(query, params)

                due_words = []
                for row in cur.fetchall():
                    card = Card.from_dict(row["card_data"])
                    retrievability = self.scheduler.get_card_retrievability(card)

                    due_words.append(
                        {
                            "word": row["word"],
                            "translation": row["translation"],
                            "phonetic": row["phonetic"],
                            "example": row["example"],
                            "usphone": row["usphone"],
                            "ukphone": row["ukphone"],
                            "definition": row["definition"],
                            "ted_videos": row["ted_videos"],
                            "exchange": row["exchange"],
                            "ai_explanation": row["ai_explanation"],
                            "scene_content": row["scene_content"],
                            "due": row["due"].isoformat(),
                            "state": State(row["state"]).name,
                            "overdue_hours": max(
                                0, (now - row["due"]).total_seconds() / 3600
                            ),
                            "retrievability": retrievability,
                        }
                    )

                return due_words

    def get_new_words(
        self, user_id: str, limit: Optional[int] = None, book_name: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取未学习过的新单词列表（last_review为NULL的单词）

        参数:
            user_id: 用户ID
            limit: 返回的最大单词数（None 表示全部）
            book_name: 单词书名称（可选，用于过滤特定单词书的单词）

        返回:
            未学习过的单词信息列表
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 构建基础查询
                # 静态内容从 global_words 获取（COALESCE 回退到 fsrs_words 以兼容旧数据）
                # AI 内容从 fsrs_words 获取（用户隔离）
                if book_name:
                    # 如果指定了单词书，JOIN global_word_books 表过滤
                    query = f"""
                        SELECT w.word,
                               COALESCE(g.translation, w.translation) as translation,
                               COALESCE(g.phonetic, w.phonetic) as phonetic,
                               w.example,
                               COALESCE(g.usphone, w.usphone) as usphone,
                               COALESCE(g.ukphone, w.ukphone) as ukphone,
                               COALESCE(g.definition, w.definition) as definition,
                               COALESCE(g.ted_videos, w.ted_videos) as ted_videos,
                               g.exchange,
                               w.ai_explanation, w.scene_content,
                               c.due, c.state, c.stability, c.difficulty, c.card_data
                        FROM {self.schema}.fsrs_cards c
                        JOIN {self.schema}.fsrs_words w ON c.word_id = w.word_id AND c.user_id = w.user_id
                        LEFT JOIN {self.schema}.global_words g ON w.word = g.word
                        JOIN {self.schema}.global_word_books gb ON w.word = gb.word
                        WHERE c.last_review IS NULL AND c.user_id = %s AND gb.book_name = %s
                        ORDER BY w.word_id ASC
                    """
                    params = (user_id, book_name)
                else:
                    # 不过滤，返回所有单词
                    query = f"""
                        SELECT w.word,
                               COALESCE(g.translation, w.translation) as translation,
                               COALESCE(g.phonetic, w.phonetic) as phonetic,
                               w.example,
                               COALESCE(g.usphone, w.usphone) as usphone,
                               COALESCE(g.ukphone, w.ukphone) as ukphone,
                               COALESCE(g.definition, w.definition) as definition,
                               COALESCE(g.ted_videos, w.ted_videos) as ted_videos,
                               g.exchange,
                               w.ai_explanation, w.scene_content,
                               c.due, c.state, c.stability, c.difficulty, c.card_data
                        FROM {self.schema}.fsrs_cards c
                        JOIN {self.schema}.fsrs_words w ON c.word_id = w.word_id AND c.user_id = w.user_id
                        LEFT JOIN {self.schema}.global_words g ON w.word = g.word
                        WHERE c.last_review IS NULL AND c.user_id = %s
                        ORDER BY w.word_id ASC
                    """
                    params = (user_id,)

                if limit:
                    query += " LIMIT %s"
                    params = params + (int(limit),)

                cur.execute(query, params)

                new_words = []
                for row in cur.fetchall():
                    card = Card.from_dict(row["card_data"])
                    retrievability = self.scheduler.get_card_retrievability(card)

                    new_words.append(
                        {
                            "word": row["word"],
                            "translation": row["translation"],
                            "phonetic": row["phonetic"],
                            "example": row["example"],
                            "usphone": row["usphone"],
                            "ukphone": row["ukphone"],
                            "definition": row["definition"],
                            "ted_videos": row["ted_videos"],
                            "exchange": row["exchange"],
                            "ai_explanation": row["ai_explanation"],
                            "scene_content": row["scene_content"],
                            "due": row["due"].isoformat(),
                            "state": State(row["state"]).name,
                            "retrievability": retrievability,
                        }
                    )

                return new_words

    def get_user_books(self, user_id: str) -> List[str]:
        """
        获取用户已加载的所有单词书列表

        参数:
            user_id: 用户ID

        返回:
            单词书名称列表
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT DISTINCT book_name
                    FROM {self.schema}.fsrs_word_books
                    WHERE user_id = %s
                    ORDER BY book_name
                """,
                    (user_id,),
                )
                return [row["book_name"] for row in cur.fetchall()]

    # ========== 全局表操作方法 ==========

    def add_word_to_global(
        self,
        word: str,
        translation: str = None,
        phonetic: str = None,
        usphone: str = None,
        ukphone: str = None,
        definition: str = None,
        ted_videos: list = None,
        exchange: str = None,
        book_name: str = None,
    ) -> bool:
        """
        添加单词到全局表（静态内容 + 单词书映射）

        参数:
            word: 单词
            translation: 中文翻译
            phonetic: 音标
            usphone: 美式音标
            ukphone: 英式音标
            definition: 英文定义
            ted_videos: TED视频实例列表
            exchange: 词形变化字符串（格式：s:campaigns/i:campaigning/p:campaigned...）
            book_name: 单词书名称

        返回:
            是否成功添加（已存在返回 False）
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 插入到 global_words（ON CONFLICT DO NOTHING）
                cur.execute(
                    f"""
                    INSERT INTO {self.schema}.global_words
                    (word, translation, phonetic, usphone, ukphone, definition, ted_videos, exchange)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (word) DO NOTHING
                    RETURNING word
                """,
                    (word, translation, phonetic, usphone, ukphone, definition,
                     json.dumps(ted_videos) if ted_videos else None, exchange),
                )
                is_new_word = cur.fetchone() is not None

                # 如果指定了单词书，添加到 global_word_books
                if book_name:
                    cur.execute(
                        f"""
                        INSERT INTO {self.schema}.global_word_books (word, book_name)
                        VALUES (%s, %s)
                        ON CONFLICT (word, book_name) DO NOTHING
                    """,
                        (word, book_name),
                    )

                return is_new_word

    def get_global_words_count(self) -> int:
        """获取全局单词表中的单词数量"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) as count FROM {self.schema}.global_words")
                return cur.fetchone()["count"]

    def get_words_to_create(self, user_id: str, book_name: str) -> List[str]:
        """
        获取用户在指定单词书中还没有创建记录的单词

        参数:
            user_id: 用户ID
            book_name: 单词书名称

        返回:
            需要创建 fsrs_words 记录的单词列表（按原始单词书顺序）
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT gb.word
                    FROM {self.schema}.global_word_books gb
                    LEFT JOIN {self.schema}.fsrs_words w ON gb.word = w.word AND w.user_id = %s
                    WHERE gb.book_name = %s
                      AND w.word_id IS NULL
                    ORDER BY gb.id ASC
                """,
                    (user_id, book_name),
                )
                return [row["word"] for row in cur.fetchall()]

    def add_word_for_user(self, word: str, user_id: str) -> int:
        """
        为用户创建单词记录（简化版，只创建 fsrs_words 和 fsrs_cards）

        前提：该单词已存在于 global_words 表中

        参数:
            word: 单词
            user_id: 用户ID

        返回:
            word_id
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 只插入 word_id, user_id, word（其他静态字段从 global_words 获取）
                cur.execute(
                    f"""
                    INSERT INTO {self.schema}.fsrs_words (user_id, word)
                    VALUES (%s, %s)
                    ON CONFLICT (word, user_id) DO NOTHING
                    RETURNING word_id
                """,
                    (user_id, word),
                )

                result = cur.fetchone()
                if result:
                    word_id = result["word_id"]
                    # 为新单词创建卡片
                    self._create_card_for_word(word_id, user_id, conn)
                else:
                    # 单词已存在，获取 word_id
                    cur.execute(
                        f"SELECT word_id FROM {self.schema}.fsrs_words WHERE word = %s AND user_id = %s",
                        (word, user_id),
                    )
                    word_id = cur.fetchone()["word_id"]

                    # 检查是否存在卡片，不存在则补建
                    cur.execute(
                        f"SELECT 1 FROM {self.schema}.fsrs_cards WHERE word_id = %s AND user_id = %s",
                        (word_id, user_id),
                    )
                    if not cur.fetchone():
                        self._create_card_for_word(word_id, user_id, conn)

                return word_id

    # ========== 用户设置方法 ==========

    def get_last_wordbook(self, user_id: str) -> dict:
        """
        获取用户上次使用的单词书

        参数:
            user_id: 用户ID

        返回:
            {'name': 'TOEFL', 'category': '出国'} 或 None
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT last_wordbook_name, last_wordbook_category
                    FROM {self.schema}.user_settings
                    WHERE user_id = %s
                """,
                    (user_id,),
                )
                row = cur.fetchone()
                if row and row["last_wordbook_name"]:
                    return {
                        "name": row["last_wordbook_name"],
                        "category": row["last_wordbook_category"],
                    }
                return None

    def set_last_wordbook(self, user_id: str, book_name: str, category: str) -> None:
        """
        保存用户上次使用的单词书

        参数:
            user_id: 用户ID
            book_name: 单词书名称
            category: 单词书分类
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.schema}.user_settings (user_id, last_wordbook_name, last_wordbook_category, updated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                        last_wordbook_name = EXCLUDED.last_wordbook_name,
                        last_wordbook_category = EXCLUDED.last_wordbook_category,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (user_id, book_name, category),
                )

    def get_pronunciation(self, user_id: str) -> str:
        """
        获取用户的发音偏好
        
        参数:
            user_id: 用户ID
        
        返回:
            'us' 或 'uk'，默认 'us'
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT pronunciation
                    FROM {self.schema}.user_settings
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                if row and row.get("pronunciation"):
                    return row["pronunciation"]
                return "us"  # 默认美式发音

    def set_pronunciation(self, user_id: str, pronunciation: str) -> None:
        """
        保存用户的发音偏好
        
        参数:
            user_id: 用户ID
            pronunciation: 'us' 或 'uk'
        """
        if pronunciation not in ("us", "uk"):
            pronunciation = "us"
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.schema}.user_settings (user_id, pronunciation, updated_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                        pronunciation = EXCLUDED.pronunciation,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, pronunciation),
                )

    def add_loaded_book(self, user_id: str, book_name: str, category: str = None) -> None:
        """
        记录用户已加载的单词书

        参数:
            user_id: 用户ID
            book_name: 单词书名称
            category: 单词书分类
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.schema}.user_loaded_books (user_id, book_name, category)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, book_name) DO UPDATE SET loaded_at = CURRENT_TIMESTAMP
                """,
                    (user_id, book_name, category),
                )

    def get_loaded_books(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户已加载的所有单词书

        参数:
            user_id: 用户ID

        返回:
            [{name, category, loaded_at}, ...]
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT book_name as name, category, loaded_at
                    FROM {self.schema}.user_loaded_books
                    WHERE user_id = %s
                    ORDER BY loaded_at DESC
                """,
                    (user_id,),
                )
                return cur.fetchall()

    def get_learning_statistics(
        self, user_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """
        获取学习统计信息

        参数:
            user_id: 用户ID
            days: 统计最近多少天的数据

        返回:
            统计信息字典
        """
        since_date = datetime.now().date() - timedelta(days=days)

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 获取总体统计
                cur.execute(
                    f"""
                    SELECT
                        COUNT(DISTINCT word_id) as total_words,
                        COUNT(DISTINCT CASE WHEN state = 2 THEN word_id END) as mastered_words,
                        COUNT(DISTINCT CASE WHEN state = 1 THEN word_id END) as learning_words
                    FROM {self.schema}.fsrs_cards
                    WHERE user_id = %s
                """,
                    (user_id,),
                )
                stats = dict(cur.fetchone())

                # 获取最近的复习统计
                cur.execute(
                    f"""
                    SELECT
                        COUNT(*) as total_reviews,
                        AVG(rating) as avg_rating,
                        COUNT(DISTINCT word_id) as words_reviewed,
                        SUM(review_duration) as total_time_ms
                    FROM {self.schema}.fsrs_review_logs
                    WHERE review_datetime::date >= %s AND user_id = %s
                """,
                    (since_date, user_id),
                )
                recent_stats = dict(cur.fetchone())
                stats.update(recent_stats)

                # 计算记忆保持率
                cur.execute(
                    f"""
                    SELECT
                        CASE
                            WHEN COUNT(*) > 0 THEN COUNT(CASE WHEN rating > 1 THEN 1 END) * 100.0 / COUNT(*)
                            ELSE 0
                        END as retention_rate
                    FROM {self.schema}.fsrs_review_logs
                    WHERE review_datetime::date >= %s AND user_id = %s
                """,
                    (since_date, user_id),
                )
                retention = cur.fetchone()
                stats["retention_rate"] = retention["retention_rate"] or 0

                return stats

    def get_today_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        获取今日学习统计（时区安全版本）

        使用数据库的 CURRENT_DATE 而不是 Python 的系统时区，
        确保在任何部署环境下都能正确统计"今天"的数据

        参数:
            user_id: 用户ID

        返回:
            统计信息字典，包含：
            - words_reviewed_today: 今日复习的唯一单词数
            - total_reviews_today: 今日总评分次数
            - avg_rating_today: 今日平均评分
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 使用数据库的 CURRENT_DATE，与数据库时区保持一致
                cur.execute(
                    f"""
                    SELECT
                        COUNT(DISTINCT word_id) as words_reviewed_today,
                        COUNT(*) as total_reviews_today,
                        COALESCE(AVG(rating), 0) as avg_rating_today,
                        COALESCE(SUM(review_duration), 0) as total_time_ms_today
                    FROM {self.schema}.fsrs_review_logs
                    WHERE review_datetime::date = CURRENT_DATE AND user_id = %s
                """,
                    (user_id,),
                )

                stats = dict(cur.fetchone())

                # 确保返回整数而不是None
                stats['words_reviewed_today'] = stats.get('words_reviewed_today', 0) or 0
                stats['total_reviews_today'] = stats.get('total_reviews_today', 0) or 0
                stats['total_time_ms_today'] = stats.get('total_time_ms_today', 0) or 0

                return stats

    def _update_daily_stats(
        self, date, rating: int, user_id: str, conn
    ):
        """更新每日统计"""
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self.schema}.fsrs_learning_stats (date, user_id, words_reviewed, average_rating)
                VALUES (%s, %s, 1, %s)
                ON CONFLICT(date, user_id) DO UPDATE SET
                    words_reviewed = {self.schema}.fsrs_learning_stats.words_reviewed + 1,
                    average_rating = ({self.schema}.fsrs_learning_stats.average_rating *
                                     {self.schema}.fsrs_learning_stats.words_reviewed + %s) /
                                     ({self.schema}.fsrs_learning_stats.words_reviewed + 1)
            """,
                (date, user_id, rating, rating),
            )

    def update_word_ai_explanation(
        self, word: str, ai_explanation: str, user_id: str
    ) -> bool:
        """
        更新单词的AI生成内容

        参数:
            word: 单词
            ai_explanation: AI生成的详细解释
            user_id: 用户ID

        返回:
            是否成功
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE {self.schema}.fsrs_words
                        SET ai_explanation = %s
                        WHERE word = %s AND user_id = %s
                        """,
                        (ai_explanation, word, user_id),
                    )
                    return cur.rowcount > 0

        except Exception as e:
            print(f"❌ 更新AI内容失败 {word}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_word_scene_content(
        self, word: str, scene_content: str, user_id: str
    ) -> bool:
        """
        更新单词的场景内容

        参数:
            word: 单词
            scene_content: 场景画面内容
            user_id: 用户ID

        返回:
            是否成功
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE {self.schema}.fsrs_words
                        SET scene_content = %s
                        WHERE word = %s AND user_id = %s
                        """,
                        (scene_content, word, user_id),
                    )
                    return cur.rowcount > 0

        except Exception as e:
            print(f"❌ 更新场景内容失败 {word}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_words_without_ai_explanation(
        self, words: List[str], user_id: str
    ) -> List[str]:
        """
        从给定的单词列表中，筛选出还没有AI内容的单词

        参数:
            words: 单词列表
            user_id: 用户ID

        返回:
            没有AI内容的单词列表
        """
        if not words:
            return []

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 使用 ANY 来查询列表中的单词
                cur.execute(
                    f"""
                    SELECT word
                    FROM {self.schema}.fsrs_words
                    WHERE word = ANY(%s) AND user_id = %s
                      AND (ai_explanation IS NULL OR ai_explanation = '')
                    """,
                    (words, user_id),
                )
                return [row["word"] for row in cur.fetchall()]

    def get_words_without_complete_content(
        self, words: List[str], user_id: str
    ) -> List[str]:
        """
        从给定的单词列表中，筛选出ai_explanation或scene_content缺失的单词

        注意：只要有任何一个字段缺失，就会返回该单词
        Worker会为这些单词重新生成两种内容（可能覆盖已有内容）

        参数:
            words: 单词列表
            user_id: 用户ID

        返回:
            内容不完整的单词列表
        """
        if not words:
            return []

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # 使用 ANY 来查询列表中的单词
                cur.execute(
                    f"""
                    SELECT word
                    FROM {self.schema}.fsrs_words
                    WHERE word = ANY(%s) AND user_id = %s
                      AND (ai_explanation IS NULL OR ai_explanation = ''
                           OR scene_content IS NULL OR scene_content = '')
                    """,
                    (words, user_id),
                )
                return [row["word"] for row in cur.fetchall()]

    def optimize_parameters(self, user_id: str) -> None:
        """
        基于历史复习记录优化 FSRS 参数
        需要先安装优化器: pip install "fsrs[optimizer]"

        注意：当前实现会更新全局 scheduler，多用户场景下需要后续改进为按用户存储优化参数

        参数:
            user_id: 用户ID，只使用该用户的复习记录进行优化
        """
        try:
            from fsrs import Optimizer

            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # 获取该用户的所有复习记录
                    cur.execute(
                        f"""
                        SELECT card_id, rating, review_datetime, review_duration
                        FROM {self.schema}.fsrs_review_logs
                        WHERE user_id = %s
                        ORDER BY card_id, review_datetime
                    """,
                        (user_id,),
                    )

                    review_logs = []
                    for row in cur.fetchall():
                        review_log = ReviewLog(
                            card_id=row["card_id"],
                            rating=Rating(row["rating"]),
                            review_datetime=row["review_datetime"],
                            review_duration=row["review_duration"],
                        )
                        review_logs.append(review_log)

                    if len(review_logs) < 512:
                        print(
                            f"复习记录不足（当前: {len(review_logs)}），需要至少512条记录后再优化"
                        )
                        print(f"提示：这是所有单词的总复习次数，不是每个单词都要512次")
                        return

                    # 优化参数
                    print("正在优化参数...")
                    optimizer = Optimizer(review_logs)
                    optimal_parameters = optimizer.compute_optimal_parameters(
                        verbose=True
                    )
                    optimal_retention = optimizer.compute_optimal_retention(
                        optimal_parameters
                    )

                    # 创建新的优化后的调度器
                    # TODO: 多用户场景下需要将优化参数持久化到数据库，按用户存储
                    self.scheduler = Scheduler(
                        parameters=optimal_parameters,
                        desired_retention=optimal_retention,
                        learning_steps=self.scheduler.learning_steps,
                        relearning_steps=self.scheduler.relearning_steps,
                        maximum_interval=self.scheduler.maximum_interval,
                        enable_fuzzing=self.scheduler.enable_fuzzing,
                    )

                    print(f"\n参数优化完成！")
                    print(f"最优记忆保持率: {optimal_retention:.2%}")
                    print(f"优化后的参数（前5个）: {optimal_parameters[:5]}")

        except ImportError:
            print("请先安装优化器: pip install 'fsrs[optimizer]'")

    def import_from_json(self, json_file: str, user_id: str):
        """
        从 JSON 文件导入单词（如 sorted_TOEFL.json）

        参数:
            json_file: JSON 文件路径
            user_id: 用户ID
        """
        with open(json_file, "r", encoding="utf-8") as f:
            words_data = json.load(f)

        imported = 0
        for item in words_data:
            if "word" in item:
                self.add_word(
                    word=item["word"],
                    translation=item.get("translation"),
                    phonetic=item.get("phonetic"),
                    example=item.get("example_sentence"),
                    difficulty_level="TOEFL",
                    user_id=user_id,
                )
                imported += 1

        print(f"成功导入 {imported} 个单词")

    def close(self):
        """关闭连接池"""
        self.pool.close()


# ============ 使用示例 ============


def demo_basic_usage():
    """基础使用演示"""
    print("=== FSRS + PostgreSQL 基础使用演示 ===\n")

    # 1. 初始化系统（从环境变量读取 DB_URI）
    system = FSRSPostgreSQLSystem()

    # 2. 添加单词
    print("添加单词...")
    system.add_word(
        word="abandon",
        translation="放弃，抛弃",
        phonetic="/əˈbændən/",
        example="Don't abandon hope.",
        difficulty_level="TOEFL",
    )

    system.add_word(
        word="ability",
        translation="能力，才能",
        phonetic="/əˈbɪləti/",
        example="She has the ability to solve complex problems.",
        difficulty_level="TOEFL",
    )

    # 3. 获取需要复习的单词
    print("\n需要复习的单词:")
    due_words = system.get_due_words()
    for word_info in due_words:
        print(f"- {word_info['word']}: {word_info['translation']}")
        print(f"  记忆概率: {word_info['retrievability']:.2%}")

    # 4. 复习单词
    print("\n复习单词 'abandon'...")
    result = system.review_word(
        word="abandon", rating=3, review_duration_ms=2500  # Good  # 2.5秒
    )

    print(f"复习结果:")
    print(f"- 下次复习: {result['next_review_date']}")
    print(f"- 间隔天数: {result['interval_days']}")
    print(f"- 当前状态: {result['state']}")
    print(f"- 难度系数: {result['difficulty']:.2f}")
    print(f"- 记忆概率: {result['retrievability']:.2%}")

    # 5. 获取学习统计
    print("\n学习统计:")
    stats = system.get_learning_statistics(days=7)
    print(f"- 总单词数: {stats['total_words']}")
    print(f"- 已掌握: {stats['mastered_words']}")
    print(f"- 学习中: {stats['learning_words']}")
    print(f"- 最近7天复习: {stats['total_reviews'] or 0} 次")
    print(f"- 记忆保持率: {stats['retention_rate']:.1f}%")

    system.close()


def demo_interactive_session():
    """交互式学习会话演示"""
    print("=== 交互式学习会话 ===\n")

    system = FSRSPostgreSQLSystem()

    # 添加一些示例单词
    sample_words = [
        {"word": "abandon", "translation": "放弃", "phonetic": "/əˈbændən/"},
        {"word": "ability", "translation": "能力", "phonetic": "/əˈbɪləti/"},
        {"word": "abroad", "translation": "在国外", "phonetic": "/əˈbrɔːd/"},
        {"word": "absence", "translation": "缺席", "phonetic": "/ˈæbsəns/"},
        {"word": "absolute", "translation": "绝对的", "phonetic": "/ˈæbsəluːt/"},
    ]

    for word_data in sample_words:
        system.add_word(**word_data)

    # 开始学习会话
    while True:
        due_words = system.get_due_words(limit=5)

        if not due_words:
            print("今天没有需要复习的单词！")
            break

        print(f"\n有 {len(due_words)} 个单词需要复习")
        print("-" * 40)

        for word_info in due_words:
            print(f"\n单词: {word_info['word']}")
            print(f"音标: {word_info['phonetic']}")
            print(f"释义: {word_info['translation']}")

            if word_info["example"]:
                print(f"例句: {word_info['example']}")

            print(f"当前记忆概率: {word_info['retrievability']:.1%}")

            # 获取用户评分
            while True:
                try:
                    rating_input = input(
                        "\n评分 (1=忘记, 2=困难, 3=记得, 4=简单, q=退出): "
                    )

                    if rating_input.lower() == "q":
                        system.close()
                        return

                    rating = int(rating_input)
                    if 1 <= rating <= 4:
                        break
                    else:
                        print("请输入 1-4 的数字")
                except ValueError:
                    print("无效输入，请输入 1-4 的数字")

            # 记录复习
            result = system.review_word(word_info["word"], rating)

            print(f"\n✓ 已记录")
            print(f"下次复习: {result['interval_days']} 天后")
            print("-" * 40)

        continue_choice = input("\n继续复习？(y/n): ")
        if continue_choice.lower() != "y":
            break

    # 显示学习统计
    print("\n今日学习统计:")
    stats = system.get_learning_statistics(days=1)
    print(f"- 复习单词数: {stats['words_reviewed'] or 0}")
    print(f"- 平均评分: {stats['avg_rating'] or 0:.1f}")

    system.close()


def demo_import_toefl():
    """演示导入 TOEFL 词汇"""
    print("=== 导入 TOEFL 词汇演示 ===\n")

    system = FSRSPostgreSQLSystem()

    # 检查是否存在 sorted_TOEFL.json
    import os

    if os.path.exists("sorted_TOEFL.json"):
        print("正在导入 sorted_TOEFL.json...")
        system.import_from_json("sorted_TOEFL.json")

        # 显示导入结果
        stats = system.get_learning_statistics()
        print(f"\n导入完成!")
        print(f"总单词数: {stats['total_words']}")

        # 获取一些需要学习的单词
        due_words = system.get_due_words(limit=10)
        print(f"\n前10个需要学习的单词:")
        for word in due_words:
            print(f"- {word['word']}: {word['translation']}")
    else:
        print("未找到 sorted_TOEFL.json 文件")
        print("创建示例 TOEFL 单词...")

        # 创建一些示例 TOEFL 单词
        toefl_samples = [
            {
                "word": "abandon",
                "translation": "放弃，抛弃",
                "difficulty_level": "TOEFL",
            },
            {
                "word": "abstract",
                "translation": "抽象的",
                "difficulty_level": "TOEFL",
            },
            {"word": "academy", "translation": "学院", "difficulty_level": "TOEFL"},
            {"word": "accelerate", "translation": "加速", "difficulty_level": "TOEFL"},
            {
                "word": "accommodate",
                "translation": "容纳，适应",
                "difficulty_level": "TOEFL",
            },
        ]

        for word_data in toefl_samples:
            system.add_word(**word_data)

        print(f"已添加 {len(toefl_samples)} 个示例单词")

    system.close()


if __name__ == "__main__":
    # 提示数据库连接信息
    db_uri = os.getenv("DB_URI") or "postgresql://localhost/langgraph_test"
    db_name = db_uri.split('/')[-1]
    print(f"💡 使用数据库: {db_name}")
    print(f"   连接字符串: {db_uri}")
    print(f"\n如需使用其他数据库，请设置环境变量 DB_URI\n")

    # 运行不同的演示
    print("选择演示模式:")
    print("1. 基础使用演示")
    print("2. 交互式学习会话")
    print("3. 导入 TOEFL 词汇")

    choice = input("\n请选择 (1/2/3): ")

    if choice == "1":
        demo_basic_usage()
    elif choice == "2":
        demo_interactive_session()
    elif choice == "3":
        demo_import_toefl()
    else:
        print("使用默认: 基础演示")
        demo_basic_usage()
