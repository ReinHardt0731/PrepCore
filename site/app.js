const downloadLink = document.getElementById("download-link");
const statusText = document.getElementById("status-text");
const carousel = document.getElementById("feature-carousel");
const dotsContainer = document.getElementById("carousel-dots");
const prevButton = document.getElementById("carousel-prev");
const nextButton = document.getElementById("carousel-next");
const slides = carousel ? Array.from(carousel.children) : [];

downloadLink.addEventListener("click", () => {
    statusText.textContent = "Starting download from dist/PrepCore.exe...";
});

if (carousel && dotsContainer && slides.length > 0) {
    const scrollToIndex = (index) => {
        const boundedIndex = Math.max(0, Math.min(index, slides.length - 1));
        const left = boundedIndex * carousel.clientWidth;
        carousel.scrollTo({ left, behavior: "smooth" });
    };

    const dots = slides.map((_, index) => {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.className = "carousel-dot";
        dot.setAttribute("aria-label", `Go to screenshot ${index + 1}`);
        dot.addEventListener("click", () => scrollToIndex(index));
        dotsContainer.appendChild(dot);
        return dot;
    });

    const updateActiveDot = () => {
        const index = Math.round(carousel.scrollLeft / carousel.clientWidth);
        dots.forEach((dot, dotIndex) => {
            dot.classList.toggle("is-active", dotIndex === index);
        });
    };

    if (prevButton) {
        prevButton.addEventListener("click", () => {
            const index = Math.round(carousel.scrollLeft / carousel.clientWidth);
            scrollToIndex(index - 1);
        });
    }

    if (nextButton) {
        nextButton.addEventListener("click", () => {
            const index = Math.round(carousel.scrollLeft / carousel.clientWidth);
            scrollToIndex(index + 1);
        });
    }

    carousel.addEventListener("scroll", updateActiveDot, { passive: true });
    window.addEventListener("resize", updateActiveDot);
    updateActiveDot();
}
