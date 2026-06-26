# ProveIt API — MVP Backend

## 🚀 راه‌اندازی

```bash
cd proveit-api
pip install flask PyJWT
python app.py
```

سرور روی `http://localhost:5000` اجرا میشه.

---

## 📡 Endpoints

### Auth
| Method | Path | توضیح |
|--------|------|-------|
| POST | `/api/auth/register` | ثبت‌نام |
| POST | `/api/auth/login` | ورود |
| GET | `/api/auth/me` | پروفایل من |

### Users
| Method | Path | توضیح |
|--------|------|-------|
| GET | `/api/users/:id` | پروفایل کاربر |
| PATCH | `/api/users/me` | ویرایش پروفایل |
| GET | `/api/users/search?q=` | جستجو |
| POST | `/api/users/:id/friend` | درخواست دوستی |
| GET | `/api/users/me/friends` | لیست دوستان |

### Challenges
| Method | Path | توضیح |
|--------|------|-------|
| GET | `/api/challenges` | لیست چالش‌ها |
| POST | `/api/challenges` | ساخت چالش جدید |
| GET | `/api/challenges/:id` | جزئیات |
| POST | `/api/challenges/:id/join` | پیوستن |
| POST | `/api/challenges/:id/complete` | اتمام + XP |
| GET | `/api/challenges/trending` | ترندها |
| GET | `/api/challenges/mine` | چالش‌های من |

### Posts / Feed
| Method | Path | توضیح |
|--------|------|-------|
| GET | `/api/posts/feed` | فید اجتماعی |
| POST | `/api/posts` | پست جدید |
| POST | `/api/posts/:id/like` | لایک |
| POST | `/api/posts/:id/cheer` | تشویق |

---

## 🔐 Authentication

همه endpoint‌ها (به جز register/login) نیاز به `Authorization: Bearer <token>` دارن.

---

## 📦 Tech Stack

- **Framework**: Flask (Python)
- **Database**: SQLite (MVP) → PostgreSQL (Production)
- **Auth**: JWT (PyJWT)
- **Deploy**: Railway / Render / Heroku

---

## 🗄️ Database Tables

- `users` — کاربران
- `challenges` — چالش‌ها (ساخته‌شده توسط کاربر)
- `user_challenges` — شرکت در چالش
- `posts` — پست‌های فید
- `friendships` — دوستی‌ها
- `messages` — پیام‌ها
- `likes` — لایک و تشویق

---

## 🔥 قدم بعدی

1. اضافه کردن Socket.io برای چت زنده
2. Battle system
3. آپلود عکس/ویدیو
4. Migration به PostgreSQL
5. Deploy روی Railway
