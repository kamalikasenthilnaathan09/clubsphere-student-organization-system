// ClubSphere Client-Side Scripts (Vanilla JS)

document.addEventListener('DOMContentLoaded', function () {
  // 1. Auto-dismiss flash alerts after 5 seconds with close button support
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(function (alert) {
    const closeBtn = alert.querySelector('.alert-close');
    const dismissAlert = () => {
      alert.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      alert.style.opacity = '0';
      alert.style.transform = 'translateY(-6px)';
      setTimeout(() => alert.remove(), 300);
    };
    if (closeBtn) {
      closeBtn.addEventListener('click', dismissAlert);
    }
    // Auto-dismiss after 5 seconds if not an error alert
    if (!alert.classList.contains('alert-danger')) {
      setTimeout(dismissAlert, 5000);
    }
  });

  // Universal Success Modal Controls (Accessibility & Handlers)
  window.closeSuccessModal = function() {
    const modal = document.getElementById('cs-universal-success-modal');
    if (modal) {
      modal.style.transition = 'opacity 0.2s ease';
      modal.style.opacity = '0';
      setTimeout(() => {
        modal.remove();
      }, 200);
    }
  };

  // Keyboard accessibility: Escape key closes modal
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' || e.keyCode === 27) {
      const successModal = document.getElementById('cs-universal-success-modal');
      if (successModal) {
        closeSuccessModal();
      }
    }
  });

  // Confetti Celebration Burst (1.5 - 2.5s duration, canvas-based, accessible)
  window.launchConfettiBurst = function() {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return; // Respect reduced-motion preference
    }

    const oldCanvas = document.getElementById('cs-confetti-canvas');
    if (oldCanvas) oldCanvas.remove();

    const canvas = document.createElement('canvas');
    canvas.id = 'cs-confetti-canvas';
    canvas.style.position = 'fixed';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.width = '100vw';
    canvas.style.height = '100vh';
    canvas.style.pointerEvents = 'none';
    canvas.style.zIndex = '99999';
    document.body.appendChild(canvas);

    const ctx = canvas.getContext('2d');
    let width = window.innerWidth;
    let height = window.innerHeight;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    const colors = [
      '#7c3aed', '#6366f1', '#3b82f6', '#0284c7',
      '#10b981', '#059669', '#f59e0b', '#ec4899', '#f43f5e'
    ];

    const particleCount = 75;
    const particles = [];

    for (let i = 0; i < particleCount; i++) {
      const isRect = Math.random() > 0.35; // 65% paper rectangles, 35% particles
      particles.push({
        x: Math.random() * width,
        y: -10 - Math.random() * 80,
        vx: (Math.random() - 0.5) * 4.2,
        vy: 2.2 + Math.random() * 4.2,
        w: isRect ? 7 + Math.random() * 6 : 4 + Math.random() * 3,
        h: isRect ? 11 + Math.random() * 8 : 4 + Math.random() * 3,
        isRect: isRect,
        color: colors[Math.floor(Math.random() * colors.length)],
        rotation: Math.random() * 360,
        rotationSpeed: (Math.random() - 0.5) * 8,
        flip: Math.random() * Math.PI,
        flipSpeed: 0.05 + Math.random() * 0.08,
        opacity: 1
      });
    }

    const duration = 2000; // ~2.0 seconds
    const startTime = performance.now();
    let animId = null;

    function renderFrame(now) {
      const elapsed = now - startTime;
      if (elapsed >= duration) {
        if (animId) cancelAnimationFrame(animId);
        if (canvas.parentNode) canvas.remove();
        return;
      }

      // Smooth fade out in the final 600ms
      const fadeStart = duration - 600;
      const globalAlpha = elapsed > fadeStart ? Math.max(0, 1 - (elapsed - fadeStart) / 600) : 1;

      ctx.clearRect(0, 0, width, height);

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.vy += 0.11; // Gravity
        p.vx *= 0.99; // Air resistance
        p.rotation += p.rotationSpeed;
        p.flip += p.flipSpeed;

        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate((p.rotation * Math.PI) / 180);
        ctx.scale(Math.cos(p.flip), 1);
        ctx.globalAlpha = p.opacity * globalAlpha;
        ctx.fillStyle = p.color;

        if (p.isRect) {
          ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        } else {
          ctx.beginPath();
          ctx.arc(0, 0, p.w / 2, 0, Math.PI * 2);
          ctx.fill();
        }

        ctx.restore();
      }

      animId = requestAnimationFrame(renderFrame);
    }

    animId = requestAnimationFrame(renderFrame);
  };

  // Outside backdrop click closes modal & auto confetti trigger on load
  const universalModal = document.getElementById('cs-universal-success-modal');
  if (universalModal) {
    universalModal.addEventListener('click', function(e) {
      if (e.target === universalModal) {
        closeSuccessModal();
      }
    });

    // Auto-focus primary button or close button for accessibility
    const primaryBtn = universalModal.querySelector('.btn-primary, .btn-secondary, .cs-modal-close-btn');
    if (primaryBtn) {
      setTimeout(() => primaryBtn.focus(), 60);
    }

    // Trigger celebratory confetti burst on successful action
    setTimeout(() => {
      launchConfettiBurst();
    }, 100);
  }

  // Also trigger confetti if server rendered badge success modal
  const pageSuccessPopup = document.getElementById('page-success-popup');
  if (pageSuccessPopup && pageSuccessPopup.style.display !== 'none') {
    setTimeout(() => {
      launchConfettiBurst();
    }, 100);
  }

  // 2. Ticket Check-in AJAX scanner (Gate Verification Console)
  const checkinForm = document.getElementById('ajax-checkin-form');
  const ticketInput = document.getElementById('ticket-input');
  const eventSelect = document.getElementById('checkin-event-select');
  const feedbackContainer = document.getElementById('checkin-feedback-container');
  const verifyBtn = document.getElementById('verify-ticket-btn');

  function playGateBeep(isSuccess) {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      gain.gain.setValueAtTime(0.08, ctx.currentTime);

      if (isSuccess) {
        osc.frequency.setValueAtTime(587.33, ctx.currentTime);
        osc.frequency.setValueAtTime(880, ctx.currentTime + 0.09);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.22);
        osc.start();
        osc.stop(ctx.currentTime + 0.22);
      } else {
        osc.frequency.setValueAtTime(220, ctx.currentTime);
        osc.frequency.setValueAtTime(165, ctx.currentTime + 0.12);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.28);
        osc.start();
        osc.stop(ctx.currentTime + 0.28);
      }
    } catch (e) {
      // Graceful fallback if Web Audio is unsupported
    }
  }

  function updateGateStats(stats) {
    if (!stats) return;
    const elChecked = document.getElementById('gate-stat-checked');
    const elRemaining = document.getElementById('gate-stat-remaining');
    const elRejected = document.getElementById('gate-stat-rejected');
    if (elChecked && stats.checked_in !== undefined) elChecked.innerText = stats.checked_in;
    if (elRemaining && stats.remaining !== undefined) elRemaining.innerText = stats.remaining;
    if (elRejected && stats.rejected !== undefined) elRejected.innerText = stats.rejected;
  }

  function showGateFeedback(isSuccess, statusType, message, ticket) {
    if (!feedbackContainer) return;
    const t = ticket || {};
    const attendee = escapeHtml(t.purchaser_name || 'Unknown Attendee');
    const ticketRef = escapeHtml(t.ticket_ref || '—');
    const eventTitle = escapeHtml(t.event_title || '—');
    const eventSchedule = escapeHtml(t.event_date ? (t.event_date + (t.event_time && t.event_time !== '—' ? ' • ' + t.event_time : '')) : '—');
    const checkinTime = escapeHtml(t.check_in_time || 'Just now');
    const staffName = escapeHtml(t.verifier_name || 'Gate Staff');

    let badgeText = 'VALID TICKET / ACCESS GRANTED';
    let cardClass = 'feedback-success';

    if (!isSuccess) {
      if (statusType === 'ALREADY_CHECKED_IN') {
        badgeText = 'ACCESS DENIED: DUPLICATE CHECK-IN';
        cardClass = 'feedback-danger';
      } else if (statusType === 'WRONG_EVENT') {
        badgeText = 'ACCESS DENIED: WRONG EVENT';
        cardClass = 'feedback-danger';
      } else if (statusType === 'INVALID') {
        badgeText = 'ACCESS DENIED: INVALID TICKET';
        cardClass = 'feedback-danger';
      } else if (statusType === 'CANCELLED' || statusType === 'CANCELLED_EVENT') {
        badgeText = 'ACCESS DENIED: INELIGIBLE TICKET';
        cardClass = 'feedback-danger';
      } else if (statusType === 'WARNING') {
        badgeText = 'GATE ATTENTION REQUIRED';
        cardClass = 'feedback-warning';
      } else {
        badgeText = 'CHECK-IN REJECTED';
        cardClass = 'feedback-danger';
      }
    }

    const iconSvg = isSuccess ? `
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20 6 9 17 4 12"></polyline>
      </svg>
    ` : `
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    `;

    feedbackContainer.innerHTML = `
      <div class="gate-feedback-card ${cardClass}">
        <div class="gate-feedback-banner">
          <div class="gate-feedback-icon-box">
            ${iconSvg}
          </div>
          <div class="gate-feedback-headline">
            <span class="gate-feedback-status-badge">${badgeText}</span>
            <h3 class="gate-feedback-attendee">${attendee}</h3>
            <p class="gate-feedback-msg">${escapeHtml(message)}</p>
          </div>
        </div>

        <div class="gate-feedback-details-grid">
          <div class="gate-detail-cell">
            <span class="detail-label">Ticket Reference</span>
            <span class="detail-value"><code>${ticketRef}</code></span>
          </div>
          <div class="gate-detail-cell">
            <span class="detail-label">Event</span>
            <span class="detail-value">${eventTitle}</span>
          </div>
          <div class="gate-detail-cell">
            <span class="detail-label">Event Schedule</span>
            <span class="detail-value">${eventSchedule}</span>
          </div>
          <div class="gate-detail-cell">
            <span class="detail-label">Verification Time & Staff</span>
            <span class="detail-value">${checkinTime} (${staffName})</span>
          </div>
        </div>
      </div>
    `;
  }

  function updateRecentVerificationsTable(ticket, isSuccess) {
    const tableBody = document.getElementById('recent-checkins-body');
    if (!tableBody || !ticket || !ticket.ticket_ref) return;

    // Check if a row with this ticket_ref already exists in the table
    const existingRow = tableBody.querySelector(`tr[data-ticket-ref="${ticket.ticket_ref}"]`);

    if (existingRow) {
      // Row already exists! Do NOT duplicate rows! Flash/highlight existing row
      const highlightClass = isSuccess ? 'row-highlight-success' : 'row-highlight-danger';
      existingRow.classList.add(highlightClass);
      existingRow.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      setTimeout(() => {
        existingRow.classList.remove(highlightClass);
      }, 2500);
      return;
    }

    // Remove empty state row if present
    const emptyRow = document.getElementById('no-checkins-row');
    if (emptyRow) emptyRow.remove();

    // Create new row
    const tr = document.createElement('tr');
    tr.setAttribute('data-ticket-ref', ticket.ticket_ref);
    tr.className = isSuccess ? 'row-highlight-success' : 'row-highlight-danger';

    const badgeClass = isSuccess ? 'badge-confirmed' : 'badge-rejected';
    const statusText = ticket.status || (isSuccess ? 'Checked In' : 'Rejected');
    const attendee = ticket.purchaser_name || 'Unknown Attendee';
    const eventTitle = ticket.event_title || '—';
    const timeStr = ticket.check_in_time || 'Just now';
    const staffStr = ticket.verifier_name || 'Gate Staff';

    tr.innerHTML = `
      <td><code>${escapeHtml(ticket.ticket_ref)}</code></td>
      <td><strong>${escapeHtml(attendee)}</strong></td>
      <td>${escapeHtml(eventTitle)}</td>
      <td><span class="badge ${badgeClass}">${escapeHtml(statusText)}</span></td>
      <td class="gate-col-time">${escapeHtml(timeStr)}</td>
      <td class="gate-col-staff">${escapeHtml(staffStr)}</td>
    `;

    tableBody.insertBefore(tr, tableBody.firstChild);

    setTimeout(() => {
      tr.classList.remove(isSuccess ? 'row-highlight-success' : 'row-highlight-danger');
    }, 2500);
  }

  if (checkinForm && ticketInput) {
    ticketInput.focus();

    if (eventSelect) {
      eventSelect.addEventListener('change', function () {
        const selectedId = this.value;
        const hiddenInput = document.getElementById('hidden-event-id');
        if (hiddenInput) hiddenInput.value = selectedId;
        const url = new URL(window.location.href);
        if (selectedId) {
          url.searchParams.set('event_id', selectedId);
        } else {
          url.searchParams.delete('event_id');
        }
        window.location.href = url.toString();
      });
    }

    let isVerifying = false;

    checkinForm.addEventListener('submit', function (e) {
      e.preventDefault();
      if (isVerifying) return; // Prevent concurrent double-submits while request in flight

      const code = ticketInput.value.trim().toUpperCase();
      const eventId = eventSelect ? eventSelect.value : '';

      if (!code) {
        showGateFeedback(false, 'WARNING', 'Please enter or scan a ticket reference code.', null);
        playGateBeep(false);
        ticketInput.focus();
        return;
      }

      isVerifying = true;
      if (verifyBtn) {
        verifyBtn.disabled = true;
        const btnText = verifyBtn.querySelector('.btn-text');
        if (btnText) btnText.innerText = 'Verifying...';
      }

      // Send asynchronous check-in request
      fetch('/api/tickets/checkin', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
          ticket_ref: code,
          event_id: eventId
        })
      })
      .then(response => response.json().then(data => ({ status: response.status, body: data })))
      .then(({ status, body }) => {
        playGateBeep(body.success);

        if (body.stats) {
          updateGateStats(body.stats);
        }

        if (body.success) {
          showGateFeedback(true, body.status, body.message, body.ticket);
          ticketInput.value = '';
          ticketInput.focus();
          if (body.ticket) {
            updateRecentVerificationsTable(body.ticket, true);
          }
        } else {
          showGateFeedback(false, body.status, body.message, body.ticket);
          ticketInput.select();
          if (body.ticket) {
            updateRecentVerificationsTable(body.ticket, false);
          }
        }
      })
      .catch(err => {
        playGateBeep(false);
        showGateFeedback(false, 'WARNING', 'Network communication error. Please try again or re-scan.', null);
        ticketInput.select();
      })
      .finally(() => {
        isVerifying = false;
        if (verifyBtn) {
          verifyBtn.disabled = false;
          const btnText = verifyBtn.querySelector('.btn-text');
          if (btnText) btnText.innerText = 'Verify Ticket';
        }
      });
    });
  }

  // 3. Simple Modal toggles
  document.querySelectorAll('[data-modal-target]').forEach(button => {
    button.addEventListener('click', () => {
      const modalId = button.getAttribute('data-modal-target');
      const modal = document.getElementById(modalId);
      if (modal) {
        modal.style.display = 'flex';
      }
    });
  });

  document.querySelectorAll('.modal-close, [data-modal-close]').forEach(button => {
    button.addEventListener('click', () => {
      const modal = button.closest('.modal-backdrop');
      if (modal) {
        modal.style.display = 'none';
      }
    });
  });

  // 4. Prevent accidental double-submission on standard forms
  document.querySelectorAll('form:not(#ajax-checkin-form):not(#ajax-event-register-form)').forEach(form => {
    form.addEventListener('submit', function () {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn && !submitBtn.disabled) {
        setTimeout(() => {
          submitBtn.disabled = true;
        }, 0);
      }
    });
  });

  // 5. Event Registration & Demo Payment Popup Handler
  const regModal = document.getElementById('event-register-modal');
  const successPopup = document.getElementById('payment-success-popup');
  const regForm = document.getElementById('ajax-event-register-form');
  const closeRegBtn = document.getElementById('close-register-modal');
  const cancelRegBtn = document.getElementById('cancel-register-modal');
  const closeSuccessBtn = document.getElementById('close-success-popup');
  const closeSuccessXBtn = document.getElementById('close-success-popup-x');
  const regErrorBox = document.getElementById('modal-register-error');

  function openRegisterModal(data) {
    if (!regModal) return;
    const eventIdInput = document.getElementById('modal-event-id');
    const titleEl = document.getElementById('modal-event-title');
    const dateVenueEl = document.getElementById('modal-event-date-venue');
    const remainingEl = document.getElementById('modal-remaining-seats');
    const memberPriceEl = document.getElementById('modal-member-price-display');
    const standardPriceEl = document.getElementById('modal-standard-price-display');

    if (eventIdInput) eventIdInput.value = data.eventId;
    if (titleEl) titleEl.innerText = data.title;
    if (dateVenueEl) dateVenueEl.innerText = `📅 ${data.date} • 📍 ${data.venue}`;
    if (remainingEl) remainingEl.innerText = `${data.remaining} Seats Left`;
    if (memberPriceEl) memberPriceEl.innerText = `₹${parseFloat(data.memberPrice).toFixed(2)} (Discounted)`;
    if (standardPriceEl) standardPriceEl.innerText = `₹${parseFloat(data.standardPrice).toFixed(2)}`;

    if (regErrorBox) {
      regErrorBox.style.display = 'none';
      regErrorBox.innerText = '';
    }
    regModal.style.display = 'flex';
  }

  function closeRegisterModal() {
    if (regModal) regModal.style.display = 'none';
  }

  function closeSuccessPopup() {
    if (successPopup) {
      successPopup.style.display = 'none';
      // Refresh to update seat counts
      window.location.reload();
    }
  }

  document.querySelectorAll('.open-register-modal-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      openRegisterModal({
        eventId: this.getAttribute('data-event-id'),
        title: this.getAttribute('data-event-title'),
        date: this.getAttribute('data-event-date'),
        venue: this.getAttribute('data-event-venue'),
        memberPrice: this.getAttribute('data-member-price') || '0',
        standardPrice: this.getAttribute('data-standard-price') || '0',
        remaining: this.getAttribute('data-remaining') || '0'
      });
    });
  });

  if (closeRegBtn) closeRegBtn.addEventListener('click', closeRegisterModal);
  if (cancelRegBtn) cancelRegBtn.addEventListener('click', closeRegisterModal);
  if (closeSuccessBtn) closeSuccessBtn.addEventListener('click', closeSuccessPopup);
  if (closeSuccessXBtn) closeSuccessXBtn.addEventListener('click', closeSuccessPopup);

  if (successPopup) {
    successPopup.addEventListener('click', function (e) {
      if (e.target === successPopup) {
        closeSuccessPopup();
      }
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && successPopup && successPopup.style.display === 'flex') {
      closeSuccessPopup();
    }
  });

  if (regForm) {
    regForm.addEventListener('submit', function (e) {
      e.preventDefault();
      const eventId = document.getElementById('modal-event-id').value;
      const attendeeName = document.getElementById('modal-attendee-name').value.trim();
      const attendeeEmail = document.getElementById('modal-attendee-email').value.trim();
      const attendeePhone = document.getElementById('modal-attendee-phone').value.trim();
      const paymentSimulation = document.getElementById('modal-payment-simulation').value;
      const submitBtn = document.getElementById('submit-register-btn');

      if (!attendeeName || !attendeeEmail) {
        if (regErrorBox) {
          regErrorBox.innerText = 'Please provide attendee name and valid email.';
          regErrorBox.style.display = 'block';
        }
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerText = 'Processing Demo Payment...';
      }
      if (regErrorBox) regErrorBox.style.display = 'none';

      fetch(`/api/events/${eventId}/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
          attendee_name: attendeeName,
          attendee_email: attendeeEmail,
          attendee_phone: attendeePhone,
          payment_simulation: paymentSimulation
        })
      })
      .then(res => res.json().then(data => ({ status: res.status, ok: res.ok, data })))
      .then(({ ok, data }) => {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerText = 'Confirm & Pay (Demo)';
        }

        if (ok && data.success) {
          closeRegisterModal();
          showPaymentSuccessPopup(data.ticket);
          launchConfettiBurst();
        } else {
          if (regErrorBox) {
            regErrorBox.innerText = data.message || 'Payment processing failed. Please try again.';
            regErrorBox.style.display = 'block';
          }
        }
      })
      .catch(err => {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerText = 'Confirm & Pay (Demo)';
        }
        if (regErrorBox) {
          regErrorBox.innerText = 'Network error. Please try again.';
          regErrorBox.style.display = 'block';
        }
      });
    });
  }

  function showPaymentSuccessPopup(ticket) {
    if (!successPopup || !ticket) return;
    const nameEl = document.getElementById('success-event-name');
    const dateVenueEl = document.getElementById('success-event-date-venue');
    const attendeeEl = document.getElementById('success-attendee');
    const amountEl = document.getElementById('success-amount');
    const payRefEl = document.getElementById('success-payment-ref');
    const ticketIdEl = document.getElementById('success-ticket-id');

    if (nameEl) nameEl.innerText = ticket.event_title || '—';
    if (dateVenueEl) dateVenueEl.innerText = `${ticket.event_date || ''} at ${ticket.event_time || ''} • ${ticket.venue || ''}`;
    if (attendeeEl) attendeeEl.innerText = `${ticket.purchaser_name} (${ticket.purchaser_email})`;
    if (amountEl) amountEl.innerText = `₹${parseFloat(ticket.amount || 0).toFixed(2)}`;
    if (payRefEl) payRefEl.innerText = ticket.payment_ref || 'DEMO-TXN-VERIFIED';
    if (ticketIdEl) ticketIdEl.innerText = ticket.ticket_ref || '—';

    const qrBox = document.getElementById('success-qr-container');
    if (qrBox && ticket.qr_svg) {
      qrBox.innerHTML = ticket.qr_svg;
    }

    const viewBtn = document.getElementById('success-view-ticket-btn');
    if (viewBtn) {
      viewBtn.href = `/tickets/badge/${ticket.ticket_ref}`;
    }

    const downloadBtn = document.getElementById('success-download-ticket-btn');
    if (downloadBtn) {
      downloadBtn.href = `/tickets/download/${ticket.ticket_ref}`;
    }

    successPopup.style.display = 'flex';
    launchConfettiBurst();
  }
});
