package com.example;

public class TextBlockTest {
    private String query = """
        SELECT *
        FROM users
        WHERE id = {placeholder}
        AND name = "John"
        /* not a comment */
        // not a comment
        """;

    private String simple = "normal string";

    private String html = """
        <html>
            <body class="main">
                <p>Hello { world }</p>
            </body>
        </html>
        """;

    public void doQuery() {
        System.out.println(query);
    }

    public String getHtml() {
        return html;
    }
}
