document.addEventListener('DOMContentLoaded', () => {
  const flashMessages = document.querySelectorAll('.flash');
  flashMessages.forEach((item) => {
    setTimeout(() => {
      item.style.opacity = '0';
      item.style.transform = 'translateY(-4px)';
      item.style.transition = 'all .4s ease';
    }, 4200);
  });
});
