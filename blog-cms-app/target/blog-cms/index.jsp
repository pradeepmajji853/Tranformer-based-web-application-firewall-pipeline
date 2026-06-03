<%@ page contentType="text/html;charset=UTF-8" language="java" %>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blog & CMS Platform</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f8f9fa;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 1rem 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }

        .nav {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 2rem;
        }

        .logo {
            font-size: 1.8rem;
            font-weight: bold;
        }

        .nav-links {
            display: flex;
            list-style: none;
            gap: 2rem;
        }

        .nav-links a {
            color: white;
            text-decoration: none;
            transition: opacity 0.3s;
        }

        .nav-links a:hover {
            opacity: 0.8;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }

        .hero {
            background: white;
            border-radius: 10px;
            padding: 3rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            text-align: center;
        }

        .hero h1 {
            color: #667eea;
            margin-bottom: 1rem;
            font-size: 2.5rem;
        }

        .hero p {
            color: #666;
            font-size: 1.1rem;
            max-width: 600px;
            margin: 0 auto;
        }

        .features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem;
            margin-bottom: 2rem;
        }

        .feature-card {
            background: white;
            border-radius: 10px;
            padding: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }

        .feature-card:hover {
            transform: translateY(-5px);
        }

        .feature-card h3 {
            color: #667eea;
            margin-bottom: 1rem;
        }

        .api-section {
            background: white;
            border-radius: 10px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .api-section h2 {
            color: #667eea;
            margin-bottom: 1.5rem;
        }

        .api-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
        }

        .api-endpoint {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 5px;
            padding: 1rem;
        }

        .method {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 3px;
            color: white;
            font-size: 0.8rem;
            font-weight: bold;
            margin-bottom: 0.5rem;
        }

        .method.get { background-color: #28a745; }
        .method.post { background-color: #007bff; }
        .method.put { background-color: #ffc107; color: #333; }
        .method.delete { background-color: #dc3545; }

        .endpoint-url {
            font-family: monospace;
            background: #e9ecef;
            padding: 0.25rem 0.5rem;
            border-radius: 3px;
            margin: 0.5rem 0;
        }

        .demo-section {
            background: white;
            border-radius: 10px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .demo-section h2 {
            color: #667eea;
            margin-bottom: 1.5rem;
        }

        .demo-forms {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem;
        }

        .demo-form {
            border: 1px solid #e9ecef;
            border-radius: 5px;
            padding: 1.5rem;
        }

        .demo-form h3 {
            color: #495057;
            margin-bottom: 1rem;
        }

        .form-group {
            margin-bottom: 1rem;
        }

        .form-group label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 500;
        }

        .form-group input,
        .form-group textarea,
        .form-group select {
            width: 100%;
            padding: 0.5rem;
            border: 1px solid #ced4da;
            border-radius: 4px;
            font-size: 1rem;
        }

        .form-group textarea {
            height: 80px;
            resize: vertical;
        }

        .btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 5px;
            cursor: pointer;
            transition: background 0.3s;
            font-size: 1rem;
        }

        .btn:hover {
            background: #5a6fd8;
        }

        .btn.secondary {
            background: #6c757d;
        }

        .btn.secondary:hover {
            background: #5a6268;
        }

        .search-section {
            background: white;
            border-radius: 10px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .search-form {
            display: flex;
            gap: 1rem;
            margin-bottom: 1rem;
        }

        .search-form input[type="text"] {
            flex: 1;
            padding: 0.75rem;
            border: 1px solid #ced4da;
            border-radius: 5px;
            font-size: 1rem;
        }

        .results {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 5px;
            padding: 1rem;
            margin-top: 1rem;
            min-height: 100px;
        }

        .footer {
            background: #343a40;
            color: white;
            text-align: center;
            padding: 2rem;
            margin-top: 2rem;
        }

        @media (max-width: 768px) {
            .nav {
                flex-direction: column;
                gap: 1rem;
            }

            .nav-links {
                gap: 1rem;
            }

            .hero h1 {
                font-size: 2rem;
            }

            .search-form {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <nav class="nav">
            <div class="logo">BlogCMS</div>
            <ul class="nav-links">
                <li><a href="#home">Home</a></li>
                <li><a href="#features">Features</a></li>
                <li><a href="#api">API</a></li>
                <li><a href="#demo">Demo</a></li>
                <li><a href="#search">Search</a></li>
            </ul>
        </nav>
    </header>

    <main class="container">
        <section id="home" class="hero">
            <h1>Blog & CMS Platform</h1>
            <p>A comprehensive content management system with blog functionality, user management, file uploads, and powerful search capabilities. Perfect for generating diverse HTTP traffic patterns for WAF training and security testing.</p>
        </section>

        <section id="features" class="features">
            <div class="feature-card">
                <h3>🏠 Blog Management</h3>
                <p>Complete CRUD operations for blog posts with categories, tags, and status management. Supports draft, published, and archived states.</p>
            </div>
            <div class="feature-card">
                <h3>💬 Comment System</h3>
                <p>Interactive comment system with moderation capabilities, spam detection, and approval workflow.</p>
            </div>
            <div class="feature-card">
                <h3>👥 User Management</h3>
                <p>Comprehensive user management with role-based access control (Admin, Editor, Author, Subscriber).</p>
            </div>
            <div class="feature-card">
                <h3>📁 File Uploads</h3>
                <p>Secure file upload system with type validation, size limits, and organized storage.</p>
            </div>
            <div class="feature-card">
                <h3>🔍 Advanced Search</h3>
                <p>Powerful search functionality across posts, users, comments, and content with filtering and pagination.</p>
            </div>
            <div class="feature-card">
                <h3>📄 Content Management</h3>
                <p>Flexible content management for pages, widgets, templates, and other site components.</p>
            </div>
        </section>

        <section id="api" class="api-section">
            <h2>API Endpoints</h2>
            <div class="api-grid">
                <div class="api-endpoint">
                    <div class="method get">GET</div>
                    <div class="endpoint-url">/blogs</div>
                    <div>List all blog posts with filtering</div>
                </div>
                <div class="api-endpoint">
                    <div class="method post">POST</div>
                    <div class="endpoint-url">/blogs</div>
                    <div>Create a new blog post</div>
                </div>
                <div class="api-endpoint">
                    <div class="method put">PUT</div>
                    <div class="endpoint-url">/blogs/{id}</div>
                    <div>Update existing blog post</div>
                </div>
                <div class="api-endpoint">
                    <div class="method delete">DELETE</div>
                    <div class="endpoint-url">/blogs/{id}</div>
                    <div>Delete a blog post</div>
                </div>
                <div class="api-endpoint">
                    <div class="method get">GET</div>
                    <div class="endpoint-url">/comments</div>
                    <div>Get comments with filtering</div>
                </div>
                <div class="api-endpoint">
                    <div class="method post">POST</div>
                    <div class="endpoint-url">/comments</div>
                    <div>Submit a new comment</div>
                </div>
                <div class="api-endpoint">
                    <div class="method get">GET</div>
                    <div class="endpoint-url">/users</div>
                    <div>List users with role filtering</div>
                </div>
                <div class="api-endpoint">
                    <div class="method post">POST</div>
                    <div class="endpoint-url">/users</div>
                    <div>Create new user account</div>
                </div>
                <div class="api-endpoint">
                    <div class="method post">POST</div>
                    <div class="endpoint-url">/upload</div>
                    <div>Upload files with validation</div>
                </div>
                <div class="api-endpoint">
                    <div class="method get">GET</div>
                    <div class="endpoint-url">/search</div>
                    <div>Search across all content</div>
                </div>
                <div class="api-endpoint">
                    <div class="method get">GET</div>
                    <div class="endpoint-url">/content</div>
                    <div>Manage site content</div>
                </div>
                <div class="api-endpoint">
                    <div class="method post">POST</div>
                    <div class="endpoint-url">/search</div>
                    <div>Advanced search with filters</div>
                </div>
            </div>
        </section>

        <section id="demo" class="demo-section">
            <h2>Interactive Demo</h2>
            <div class="demo-forms">
                <div class="demo-form">
                    <h3>Create Blog Post</h3>
                    <form id="blogForm">
                        <div class="form-group">
                            <label for="blogTitle">Title:</label>
                            <input type="text" id="blogTitle" name="title" placeholder="Enter blog title">
                        </div>
                        <div class="form-group">
                            <label for="blogContent">Content:</label>
                            <textarea id="blogContent" name="content" placeholder="Write your blog content..."></textarea>
                        </div>
                        <div class="form-group">
                            <label for="blogCategory">Category:</label>
                            <select id="blogCategory" name="category">
                                <option value="technology">Technology</option>
                                <option value="programming">Programming</option>
                                <option value="design">Design</option>
                                <option value="business">Business</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="blogTags">Tags (comma-separated):</label>
                            <input type="text" id="blogTags" name="tags" placeholder="java, tutorial, programming">
                        </div>
                        <button type="submit" class="btn">Create Post</button>
                    </form>
                </div>

                <div class="demo-form">
                    <h3>Add Comment</h3>
                    <form id="commentForm">
                        <div class="form-group">
                            <label for="commentAuthor">Name:</label>
                            <input type="text" id="commentAuthor" name="author" placeholder="Your name">
                        </div>
                        <div class="form-group">
                            <label for="commentEmail">Email:</label>
                            <input type="email" id="commentEmail" name="email" placeholder="your@email.com">
                        </div>
                        <div class="form-group">
                            <label for="commentContent">Comment:</label>
                            <textarea id="commentContent" name="content" placeholder="Write your comment..."></textarea>
                        </div>
                        <input type="hidden" name="postId" value="1">
                        <button type="submit" class="btn">Post Comment</button>
                    </form>
                </div>

                <div class="demo-form">
                    <h3>File Upload</h3>
                    <form id="uploadForm" enctype="multipart/form-data">
                        <div class="form-group">
                            <label for="fileInput">Choose File:</label>
                            <input type="file" id="fileInput" name="file" accept=".jpg,.jpeg,.png,.gif,.pdf,.doc,.docx,.txt,.zip">
                        </div>
                        <button type="submit" class="btn">Upload File</button>
                    </form>
                </div>

                <div class="demo-form">
                    <h3>User Registration</h3>
                    <form id="userForm">
                        <div class="form-group">
                            <label for="username">Username:</label>
                            <input type="text" id="username" name="username" placeholder="username">
                        </div>
                        <div class="form-group">
                            <label for="email">Email:</label>
                            <input type="email" id="email" name="email" placeholder="user@example.com">
                        </div>
                        <div class="form-group">
                            <label for="displayName">Display Name:</label>
                            <input type="text" id="displayName" name="displayName" placeholder="Full Name">
                        </div>
                        <div class="form-group">
                            <label for="role">Role:</label>
                            <select id="role" name="role">
                                <option value="subscriber">Subscriber</option>
                                <option value="author">Author</option>
                                <option value="editor">Editor</option>
                                <option value="admin">Admin</option>
                            </select>
                        </div>
                        <button type="submit" class="btn">Create User</button>
                    </form>
                </div>
            </div>
        </section>

        <section id="search" class="search-section">
            <h2>Search & Discovery</h2>
            <div class="search-form">
                <input type="text" id="searchQuery" placeholder="Search posts, users, comments, content...">
                <select id="searchType">
                    <option value="">All Types</option>
                    <option value="posts">Posts</option>
                    <option value="users">Users</option>
                    <option value="comments">Comments</option>
                    <option value="content">Content</option>
                </select>
                <button id="searchBtn" class="btn">Search</button>
            </div>
            
            <div class="form-group">
                <label for="searchFilters">Advanced Filters:</label>
                <input type="text" id="searchFilters" placeholder="category:technology author:john status:published">
            </div>
            
            <button id="advancedSearchBtn" class="btn secondary">Advanced Search</button>
            
            <div id="searchResults" class="results">
                <p>Search results will appear here...</p>
            </div>
        </section>
    </main>

    <footer class="footer">
        <p>&copy; 2024 Blog & CMS Platform. Designed for WAF training and security testing.</p>
    </footer>

    <script>
        // Blog post form submission
        document.getElementById('blogForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            fetch('/blog-cms/blog', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                alert('Blog post created successfully!');
                this.reset();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error creating blog post');
            });
        });

        // Comment form submission
        document.getElementById('commentForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            fetch('/blog-cms/comments', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                alert('Comment submitted successfully!');
                this.reset();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error submitting comment');
            });
        });

        // File upload form submission
        document.getElementById('uploadForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            
            fetch('/blog-cms/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                alert('File uploaded successfully!');
                this.reset();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error uploading file');
            });
        });

        // User registration form submission
        document.getElementById('userForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            formData.append('password', 'default123'); // Default password
            
            fetch('/blog-cms/users', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                alert('User created successfully!');
                this.reset();
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error creating user');
            });
        });

        // Basic search
        document.getElementById('searchBtn').addEventListener('click', function() {
            const query = document.getElementById('searchQuery').value;
            const type = document.getElementById('searchType').value;
            
            if (!query.trim()) {
                alert('Please enter a search query');
                return;
            }
            
            const params = new URLSearchParams({ q: query });
            if (type) params.append('type', type);
            
            fetch(`/blog-cms/search?${params}`)
            .then(response => response.json())
            .then(data => {
                displaySearchResults(data);
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('searchResults').innerHTML = '<p>Error performing search</p>';
            });
        });

        // Advanced search
        document.getElementById('advancedSearchBtn').addEventListener('click', function() {
            const query = document.getElementById('searchQuery').value;
            const filters = document.getElementById('searchFilters').value;
            
            if (!query.trim()) {
                alert('Please enter a search query');
                return;
            }
            
            const formData = new FormData();
            formData.append('query', query);
            formData.append('filters', filters);
            formData.append('sortBy', 'date');
            formData.append('sortOrder', 'desc');
            
            fetch('/blog-cms/search', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                displaySearchResults(data);
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('searchResults').innerHTML = '<p>Error performing advanced search</p>';
            });
        });

        function displaySearchResults(data) {
            const resultsDiv = document.getElementById('searchResults');
            
            if (data.results && data.results.length > 0) {
                let html = `<h4>Found ${data.total} results for "${data.query}"</h4>`;
                
                data.results.forEach(result => {
                    html += `
                        <div style="border-bottom: 1px solid #dee2e6; padding: 1rem 0;">
                            <h5>${result.title} <span style="color: #6c757d; font-size: 0.8rem;">(${result.type})</span></h5>
                            <p>${result.description}</p>
                            <small>By ${result.author} on ${result.date}</small>
                            ${result.metadata ? `<br><small>Tags: ${result.metadata}</small>` : ''}
                        </div>
                    `;
                });
                
                resultsDiv.innerHTML = html;
            } else {
                resultsDiv.innerHTML = `<p>No results found for "${data.query}"</p>`;
            }
        }

        // Enter key search
        document.getElementById('searchQuery').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('searchBtn').click();
            }
        });

        // Generate some sample traffic on page load
        window.addEventListener('load', function() {
            // Simulate some API calls for training data
            setTimeout(() => {
                fetch('/blog-cms/blog?page=1&limit=5').catch(() => {});
                fetch('/blog-cms/users?role=author').catch(() => {});
                fetch('/blog-cms/comments?status=approved').catch(() => {});
                fetch('/blog-cms/content?type=page').catch(() => {});
            }, 1000);
        });
    </script>
</body>
</html>
