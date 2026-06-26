from flask import Flask, render_template, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

app.secret_key = "campusforum"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///forum.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# =========================
# GLOBAL TEMPLATE VARIABLES
# =========================

@app.context_processor
def inject_globals():

    theme = session.get('theme', 'light')

    unread_count = 0

    if 'username' in session:
        unread_count = Notification.query.filter_by(
            username=session['username'],
            is_read=False
        ).count()

    return {'theme': theme, 'unread_count': unread_count}


# =========================
# DATABASE TABLES
# =========================

class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    email = db.Column(db.String(100))
    password = db.Column(db.String(100))
    bio = db.Column(db.Text)
    profile_pic = db.Column(db.String(200))


class Post(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    username = db.Column(db.String(100))
    likes = db.Column(db.Integer, default=0)
    image = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Comment(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer)
    username = db.Column(db.String(100))
    comment = db.Column(db.Text)


class Follow(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    follower = db.Column(db.String(100))     # the one who follows
    following = db.Column(db.String(100))    # the one being followed


class Notification(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))      # who receives it
    message = db.Column(db.String(300))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Bookmark(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    post_id = db.Column(db.Integer)


# =========================
# HOME PAGE
# =========================

@app.route('/')
def home():

    search = request.args.get('search')

    if search:
        posts = Post.query.filter(
            Post.title.contains(search)
        ).order_by(Post.id.desc()).all()
    else:
        posts = Post.query.order_by(Post.id.desc()).all()

    username = session.get('username')

    comments = Comment.query.all()

    total_users = User.query.count()
    total_posts = Post.query.count()
    total_comments = Comment.query.count()

    bookmarked_ids = []

    if username:
        bookmarked_ids = [
            b.post_id for b in Bookmark.query.filter_by(username=username).all()
        ]

    return render_template(
        "index.html",
        posts=posts,
        username=username,
        comments=comments,
        total_users=total_users,
        total_posts=total_posts,
        total_comments=total_comments,
        bookmarked_ids=bookmarked_ids
    )


# =========================
# REGISTER
# =========================

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        image = request.files.get('profile_pic')

        filename = ""

        if image and image.filename != "":
            filename = image.filename
            image.save("static/uploads/" + filename)

        user = User(
            username=request.form['username'],
            email=request.form['email'],
            password=request.form['password'],
            bio=request.form['bio'],
            profile_pic=filename
        )

        db.session.add(user)
        db.session.commit()

        return redirect('/')

    return render_template("register.html")


# =========================
# LOGIN
# =========================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        user = User.query.filter_by(
            username=request.form['username'],
            password=request.form['password']
        ).first()

        if user:
            session['username'] = user.username
            return redirect('/')

        return "Invalid Username or Password"

    return render_template("login.html")


# =========================
# LOGOUT
# =========================

@app.route('/logout')
def logout():

    session.pop('username', None)
    return redirect('/')


# =========================
# CREATE POST
# =========================

@app.route('/create_post', methods=['GET', 'POST'])
def create_post():

    if 'username' not in session:
        return redirect('/login')

    if request.method == 'POST':

        image = request.files.get('post_image')

        filename = ""

        if image and image.filename != "":
            filename = image.filename
            image.save("static/uploads/" + filename)

        post = Post(
            title=request.form['title'],
            content=request.form['content'],
            username=session['username'],
            image=filename
        )

        db.session.add(post)
        db.session.commit()

        return redirect('/')

    return render_template("create_post.html")


# =========================
# DELETE POST
# =========================

@app.route('/delete_post/<int:id>')
def delete_post(id):

    post = Post.query.get(id)

    if post and post.username == session.get('username'):
        db.session.delete(post)
        db.session.commit()

    return redirect('/')


# =========================
# EDIT POST
# =========================

@app.route('/edit_post/<int:id>', methods=['GET', 'POST'])
def edit_post(id):

    post = Post.query.get(id)

    if not post:
        return redirect('/')

    if post.username != session.get('username'):
        return redirect('/')

    if request.method == 'POST':
        post.title = request.form['title']
        post.content = request.form['content']
        db.session.commit()
        return redirect('/')

    return render_template("edit_post.html", post=post)


# =========================
# COMMENT
# =========================

@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):

    if 'username' not in session:
        return redirect('/login')

    new_comment = Comment(
        post_id=post_id,
        username=session['username'],
        comment=request.form['comment']
    )

    db.session.add(new_comment)
    db.session.commit()

    post = Post.query.get(post_id)

    if post and post.username != session['username']:
        notif = Notification(
            username=post.username,
            message=f"{session['username']} commented on your post '{post.title}'"
        )
        db.session.add(notif)
        db.session.commit()

    return redirect('/')


# =========================
# LIKE POST
# =========================

@app.route('/like_post/<int:id>')
def like_post(id):

    post = Post.query.get(id)

    if post:

        post.likes += 1
        db.session.commit()

        liker = session.get('username')

        if liker and liker != post.username:
            notif = Notification(
                username=post.username,
                message=f"{liker} liked your post '{post.title}'"
            )
            db.session.add(notif)
            db.session.commit()

    return redirect('/')


# =========================
# BOOKMARK
# =========================

@app.route('/bookmark/<int:post_id>')
def bookmark(post_id):

    if 'username' not in session:
        return redirect('/login')

    existing = Bookmark.query.filter_by(
        username=session['username'],
        post_id=post_id
    ).first()

    if existing:
        db.session.delete(existing)
    else:
        db.session.add(Bookmark(username=session['username'], post_id=post_id))

    db.session.commit()

    return redirect(request.referrer or '/')


@app.route('/bookmarks')
def bookmarks():

    if 'username' not in session:
        return redirect('/login')

    saved = Bookmark.query.filter_by(username=session['username']).all()
    post_ids = [b.post_id for b in saved]

    posts = Post.query.filter(Post.id.in_(post_ids)).order_by(Post.id.desc()).all()

    return render_template("bookmarks.html", posts=posts)


# =========================
# OWN PROFILE PAGE
# =========================

@app.route('/profile')
def profile():

    if 'username' not in session:
        return redirect('/login')

    user = User.query.filter_by(username=session['username']).first()
    posts = Post.query.filter_by(username=session['username']).order_by(Post.id.desc()).all()

    followers_count = Follow.query.filter_by(following=user.username).count()
    following_count = Follow.query.filter_by(follower=user.username).count()

    return render_template(
        'profile.html',
        user=user,
        posts=posts,
        total_posts=len(posts),
        followers_count=followers_count,
        following_count=following_count
    )


# =========================
# EDIT PROFILE
# =========================

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():

    if 'username' not in session:
        return redirect('/login')

    user = User.query.filter_by(username=session['username']).first()

    if request.method == 'POST':

        user.bio = request.form['bio']

        image = request.files.get('profile_pic')

        if image and image.filename != "":
            filename = image.filename
            image.save("static/uploads/" + filename)
            user.profile_pic = filename

        db.session.commit()

        return redirect('/profile')

    return render_template('edit_profile.html', user=user)


# =========================
# PUBLIC USER PROFILE
# =========================

@app.route('/user/<username>')
def user_profile(username):

    user = User.query.filter_by(username=username).first()

    if not user:
        return "User not found"

    posts = Post.query.filter_by(username=username).order_by(Post.id.desc()).all()

    followers_count = Follow.query.filter_by(following=username).count()
    following_count = Follow.query.filter_by(follower=username).count()

    is_following = False
    current_user = session.get('username')

    if current_user:
        is_following = Follow.query.filter_by(
            follower=current_user,
            following=username
        ).first() is not None

    return render_template(
        'user_profile.html',
        user=user,
        posts=posts,
        total_posts=len(posts),
        followers_count=followers_count,
        following_count=following_count,
        is_following=is_following,
        username=current_user
    )


# =========================
# FOLLOW / UNFOLLOW
# =========================

@app.route('/follow/<username>')
def follow(username):

    current_user = session.get('username')

    if not current_user:
        return redirect('/login')

    if current_user != username:

        existing = Follow.query.filter_by(
            follower=current_user,
            following=username
        ).first()

        if not existing:

            db.session.add(Follow(follower=current_user, following=username))

            notif = Notification(
                username=username,
                message=f"{current_user} started following you"
            )
            db.session.add(notif)
            db.session.commit()

    return redirect('/user/' + username)


@app.route('/unfollow/<username>')
def unfollow(username):

    current_user = session.get('username')

    if not current_user:
        return redirect('/login')

    existing = Follow.query.filter_by(
        follower=current_user,
        following=username
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()

    return redirect('/user/' + username)


# =========================
# NOTIFICATIONS
# =========================

@app.route('/notifications')
def notifications():

    if 'username' not in session:
        return redirect('/login')

    notifs = Notification.query.filter_by(
        username=session['username']
    ).order_by(Notification.id.desc()).all()

    for n in notifs:
        n.is_read = True

    db.session.commit()

    return render_template('notifications.html', notifications=notifs)


# =========================
# TOGGLE THEME
# =========================

@app.route('/toggle_theme')
def toggle_theme():

    if session.get('theme') == 'dark':
        session['theme'] = 'light'
    else:
        session['theme'] = 'dark'

    return redirect(request.referrer or '/')


# =========================
# CREATE DATABASE
# =========================

with app.app_context():
    db.create_all()


# =========================
# RUN APP
# =========================

if __name__ == "__main__":
    app.run(debug=True)