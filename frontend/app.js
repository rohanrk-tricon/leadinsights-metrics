// Custom Markdown Renderer Overrides for Better Styling
const renderer = new marked.Renderer();
renderer.table = function (header, body) {
    return `<div class="overflow-x-auto my-6"><table class="min-w-full divide-y divide-gray-200 text-sm"><thead class="bg-gray-50">${header}</thead><tbody class="divide-y divide-gray-200 bg-white">${body}</tbody></table></div>`;
};
renderer.th = function (content) {
    return `<th scope="col" class="px-3 py-3.5 text-left text-sm font-semibold text-gray-900">${content}</th>`;
};
renderer.td = function (content) {
    return `<td class="whitespace-nowrap px-3 py-4 text-sm text-gray-500">${content}</td>`;
};

marked.setOptions({
    renderer: renderer,
    breaks: true,
    gfm: true
});

document.addEventListener('alpine:init', () => {
    Alpine.data('appData', () => ({
        query: '',
        isLoading: false,
        isIngesting: false,
        response: null,
        queryType: null,
        rawData: null,
        sqlQuery: null,
        showRaw: false,
        showSql: false,

        get formattedResponse() {
            if (!this.response) return '';
            return marked.parse(this.response);
        },

        init() {
            // Auto-focus logic could go here
            this.$nextTick(() => {
                this.$refs.searchInput.focus();
            });
        },

        async submitQuery() {
            if (!this.query.trim()) return;

            this.isLoading = true;
            this.response = null;
            this.queryType = null;
            this.rawData = null;
            this.sqlQuery = null;
            this.showRaw = false;
            this.showSql = false;

            try {
                // In production, this URL should be relative or read from env.
                const res = await fetch('http://localhost:8000/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question: this.query })
                });

                if (!res.ok) {
                    throw new Error(`Server returned ${res.status}`);
                }

                const data = await res.json();
                this.queryType = data.query_type;
                this.response = data.response;
                this.rawData = data.raw_data;
                console.log("API Response received:", data)
                if (data.sql_query) {
                    console.log("SQL Query extracted:", data.sql_query)
                    this.sqlQuery = data.sql_query.replace(/\s+/g, ' ').trim();
                } else {
                    this.sqlQuery = null;
                }

            } catch (error) {
                console.error("Query Error:", error);
                this.response = `**Error:** Let's double check that the backend server is running on port 8000.\n\n\`${error.message}\``;
                this.queryType = 'ERROR';
            } finally {
                this.isLoading = false;
                // Re-initialize icons inside new DOM content
                this.$nextTick(() => {
                    if (window.lucide) lucide.createIcons();
                });
            }
        },

        async triggerIngest() {
            this.isIngesting = true;
            try {
                const res = await fetch('http://localhost:8000/ingest', { method: 'POST' });
                if (!res.ok) throw new Error("Ingest trigger failed");
                // Visual feedback could be added here
            } catch (error) {
                console.error("Ingest Error:", error);
                alert("Could not trigger ingestion pipeline.");
            } finally {
                // Reset after a simulated timeout for UX
                setTimeout(() => { this.isIngesting = false }, 3000);
            }
        }
    }))
});
