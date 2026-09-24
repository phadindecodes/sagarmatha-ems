/**
 * public.js - Public School Website Functionality
 * Shree Sagarmatha Secondary School, Bhadrapur 2, Jhapa
 */

document.addEventListener('DOMContentLoaded', () => {
  loadPublicNotices();

  // Inquiry Form Handler
  const inquiryForm = document.getElementById('public-inquiry-form');
  if (inquiryForm) {
    inquiryForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = inquiryForm.querySelector('button[type="submit"]');
      const originalText = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Submitting...';

      const formData = {
        applicant_name: inquiryForm.applicant_name.value.trim(),
        applying_class: inquiryForm.applying_class.value,
        guardian_name: inquiryForm.guardian_name.value.trim(),
        phone: inquiryForm.phone.value.trim(),
        email: inquiryForm.email.value.trim(),
        address: inquiryForm.address.value.trim(),
        previous_school: inquiryForm.previous_school.value.trim(),
        message: inquiryForm.message.value.trim()
      };

      try {
        const res = await fetch('/api/inquiries', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData)
        });
        const result = await res.json();
        if (result.success) {
          showToast('Inquiry submitted! Our administration will contact you shortly.', 'success');
          inquiryForm.reset();
        } else {
          showToast(result.error || 'Failed to submit inquiry', 'error');
        }
      } catch (err) {
        showToast('Network error submitting inquiry', 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = originalText;
      }
    });
  }
});

async function loadPublicNotices(category = 'All') {
  const container = document.getElementById('public-notices-container');
  if (!container) return;

  container.innerHTML = '<div style="text-align:center; padding: 2rem; color: #64748b;">Loading notices...</div>';

  try {
    const url = category === 'All' ? '/api/notices' : `/api/notices?category=${category}`;
    const res = await fetch(url);
    const notices = await res.json();

    if (!notices || notices.length === 0) {
      container.innerHTML = '<div style="text-align:center; padding: 2rem; color: #64748b;">No notices currently published.</div>';
      return;
    }

    container.innerHTML = notices.map(n => `
      <div class="notice-card ${n.is_pinned ? 'pinned' : ''}">
        <div style="flex: 1;">
          <div style="display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.4rem;">
            ${n.is_pinned ? '<span class="badge badge-warning">📌 Pinned</span>' : ''}
            <span class="badge badge-info">${n.category}</span>
            <span style="font-size: 0.78rem; color: #64748b;">📅 ${n.posted_date}</span>
          </div>
          <h4 style="font-size: 1.05rem; font-weight: 700; color: #0f172a; margin-bottom: 0.35rem;">${n.title}</h4>
          <p style="font-size: 0.88rem; color: #334155; line-height: 1.5;">${n.content}</p>
        </div>
        ${n.file_attachment ? `
          <div>
            <button class="btn btn-secondary btn-sm" onclick="showToast('Downloading notice attachment...', 'info')">
              📥 Attachment
            </button>
          </div>
        ` : ''}
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = '<div style="color: red; padding: 1rem;">Failed to load notices.</div>';
  }
}

function filterAcademicLevel(level) {
  const tabs = document.querySelectorAll('.academic-tab-btn');
  tabs.forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');

  const cards = document.querySelectorAll('.program-card');
  cards.forEach(card => {
    if (level === 'all' || card.dataset.level === level) {
      card.style.display = 'block';
    } else {
      card.style.display = 'none';
    }
  });
}

// ----------------------------------------------------------------------------
// Photo Gallery & Lightbox Viewer
// ----------------------------------------------------------------------------
let galleryPhotosCache = [];

document.addEventListener('DOMContentLoaded', () => {
  loadPublicGallery();
});

async function loadPublicGallery(category = 'All') {
  const container = document.getElementById('public-gallery-grid');
  if (!container) return;

  container.innerHTML = '<div style="text-align: center; grid-column: 1/-1; padding: 2rem; color: #64748b;">Loading photo gallery...</div>';

  try {
    const url = category === 'All' ? '/api/gallery' : `/api/gallery?category=${encodeURIComponent(category)}`;
    const res = await fetch(url);
    const photos = await res.json();
    galleryPhotosCache = photos;

    if (!photos || photos.length === 0) {
      container.innerHTML = '<div style="text-align: center; grid-column: 1/-1; padding: 2.5rem; color: #64748b;">No photos in this category yet.</div>';
      return;
    }

    container.innerHTML = photos.map(p => `
      <div class="gallery-card" onclick="openGalleryLightbox(${p.id})">
        <div class="gallery-card-thumb">
          <img src="${p.image_url}" alt="${p.title}" loading="lazy">
          <span class="gallery-overlay-badge">${p.category}</span>
        </div>
        <div class="gallery-card-body">
          <div class="gallery-card-category">${p.category}</div>
          <h4 class="gallery-card-title">${p.title}</h4>
          ${p.title_np ? `<div class="gallery-card-title-np">${p.title_np}</div>` : ''}
          <p class="gallery-card-caption">${p.caption || ''}</p>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Failed to load gallery photos:', err);
    container.innerHTML = '<div style="text-align: center; grid-column: 1/-1; color: red; padding: 2rem;">Failed to load photo gallery.</div>';
  }
}

function filterGallery(category, btn) {
  document.querySelectorAll('.gallery-filter-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  loadPublicGallery(category);
}

function openGalleryLightbox(photoId) {
  const photo = galleryPhotosCache.find(p => p.id === photoId);
  if (!photo) return;

  const imgEl = document.getElementById('lightbox-img');
  const catEl = document.getElementById('lightbox-category');
  const titleEl = document.getElementById('lightbox-title');
  const titleNpEl = document.getElementById('lightbox-title-np');
  const capEl = document.getElementById('lightbox-caption');

  if (imgEl) imgEl.src = photo.image_url;
  if (catEl) catEl.textContent = photo.category;
  if (titleEl) titleEl.textContent = photo.title;
  if (titleNpEl) titleNpEl.textContent = photo.title_np || '';
  if (capEl) capEl.textContent = `${photo.caption || ''} ${photo.caption_np ? '(' + photo.caption_np + ')' : ''}`;

  openModal('gallery-lightbox-modal');
}

function closeGalleryLightbox(e) {
  if (e.target.id === 'gallery-lightbox-modal') {
    closeModal('gallery-lightbox-modal');
  }
}
