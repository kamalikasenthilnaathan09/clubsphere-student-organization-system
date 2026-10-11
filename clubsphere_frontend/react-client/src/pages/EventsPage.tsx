import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type { EventItem, Ticket } from '../types';
import { Modal } from '../components/common/Modal';
import confetti from 'canvas-confetti';
import QRCode from 'qrcode';
import {
  Calendar,
  Ticket as TicketIcon,
  Plus,
  QrCode,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  MapPin,
  Users,
  Search,
  DollarSign,
  ShieldCheck,
  RotateCcw,
} from 'lucide-react';

const TicketQrCodeView: React.FC<{ ticket: Ticket }> = ({ ticket }) => {
  const [dataUrl, setDataUrl] = useState<string | null>(ticket.qrCodeDataUrl || null);

  useEffect(() => {
    if (ticket.qrCodeDataUrl) {
      setDataUrl(ticket.qrCodeDataUrl);
      return;
    }
    // Fallback dynamic QR generation
    QRCode.toDataURL(ticket.ticketCode, {
      margin: 1,
      width: 160,
      color: { dark: '#0f172a', light: '#ffffff' },
    })
      .then((url) => setDataUrl(url))
      .catch(() => setDataUrl(null));
  }, [ticket.ticketCode, ticket.qrCodeDataUrl]);

  if (dataUrl) {
    return <img src={dataUrl} alt={`QR for ${ticket.ticketCode}`} className="w-16 h-16 object-contain" />;
  }

  return <QrCode className="w-16 h-16 text-slate-800" />;
};

export const EventsPage: React.FC = () => {
  const { role, user } = useAuth();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<'DISCOVER' | 'MY_TICKETS' | 'SCANNER'>('DISCOVER');
  const [selectedEvent, setSelectedEvent] = useState<EventItem | null>(null);

  // Modals state
  const [isBookModalOpen, setIsBookModalOpen] = useState(false);
  const [selectedTicketType, setSelectedTicketType] = useState<any>(null);
  const [bookingQty, setBookingQty] = useState(1);
  const [attendeeName, setAttendeeName] = useState(user?.fullName || '');
  const [attendeeEmail, setAttendeeEmail] = useState(user?.email || '');

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newVenue, setNewVenue] = useState('Campus Main Hall');
  const [newCapacity, setNewCapacity] = useState(100);
  const [newStartDate, setNewStartDate] = useState('');
  const [newEndDate, setNewEndDate] = useState('');
  const [newMemberPrice, setNewMemberPrice] = useState(10);
  const [newNonMemberPrice, setNewNonMemberPrice] = useState(25);

  // Scanner state
  const [scanTicketCode, setScanTicketCode] = useState('');
  const [scanResult, setScanResult] = useState<any>(null);

  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const canManageEvents = ['CLUB_ADMIN', 'SUPER_ADMIN', 'EVENT_MANAGER'].includes(role);
  const canScan = ['CLUB_ADMIN', 'SUPER_ADMIN', 'EVENT_MANAGER', 'VOLUNTEER'].includes(role);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Queries
  const { data: events = [], isLoading: eventsLoading } = useQuery<EventItem[]>({
    queryKey: ['events'],
    queryFn: () => api.listEvents(),
  });

  const { data: myTickets = [], refetch: refetchMyTickets } = useQuery<Ticket[]>({
    queryKey: ['myTickets'],
    queryFn: () => api.getUserTickets(),
  });

  // Booking action
  const handleBook = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEvent || !selectedTicketType) return;
    try {
      const res = await api.bookTicket(selectedEvent.id, {
        ticketTypeId: selectedTicketType.id,
        quantity: bookingQty,
        attendeeName,
        attendeeEmail,
      });

      confetti({
        particleCount: 100,
        spread: 70,
        origin: { y: 0.6 },
      });

      queryClient.invalidateQueries({ queryKey: ['events'] });
      queryClient.invalidateQueries({ queryKey: ['myTickets'] });
      setIsBookModalOpen(false);
      showToast(`Booking confirmed! Ticket code: ${res.tickets[0]?.ticketCode}`);
      setActiveTab('MY_TICKETS');
    } catch (err: any) {
      alert(`Booking error: ${err.message}`);
    }
  };

  // Create Event action
  const handleCreateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const start = new Date(newStartDate || Date.now() + 7 * 86400000);
      const end = new Date(newEndDate || start.getTime() + 4 * 3600000);

      await api.createEvent({
        title: newTitle,
        description: newDesc,
        venue: newVenue,
        capacity: Number(newCapacity),
        startDate: start.toISOString(),
        endDate: end.toISOString(),
        registrationOpensAt: new Date().toISOString(),
        registrationClosesAt: start.toISOString(),
        ticketTypes: [
          {
            name: 'Standard Admission',
            memberPrice: Number(newMemberPrice),
            nonMemberPrice: Number(newNonMemberPrice),
            totalQuantity: Number(newCapacity),
          },
        ],
      });

      queryClient.invalidateQueries({ queryKey: ['events'] });
      setIsCreateModalOpen(false);
      showToast('New event published successfully!');
    } catch (err: any) {
      alert(`Failed to create event: ${err.message}`);
    }
  };

  // Check-In Scan Action
  const handleCheckIn = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedEvent || !scanTicketCode.trim()) return;

    try {
      const res = await api.checkInTicket(selectedEvent.id, {
        ticketCode: scanTicketCode.trim(),
        checkInMethod: 'QR_SCAN',
      });
      setScanResult(res);
      queryClient.invalidateQueries({ queryKey: ['events'] });
      refetchMyTickets();
    } catch (err: any) {
      setScanResult(err.body || { success: false, validationStatus: 'ERROR', message: err.message });
    }
  };

  // Cancel Booking
  const handleCancelBooking = async (bookingId: string) => {
    if (!confirm('Are you sure you want to cancel this booking? Ticket inventory will be restored.')) return;
    try {
      await api.cancelBooking(bookingId);
      refetchMyTickets();
      queryClient.invalidateQueries({ queryKey: ['events'] });
      showToast('Booking cancelled and inventory returned to event pool');
    } catch (err: any) {
      alert(`Cancellation failed: ${err.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 glass-panel bg-navy-900 border border-teal-500/40 text-slate-100 px-4 py-3 rounded-2xl shadow-2xl flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-teal-400" />
          <span className="text-sm font-semibold">{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 flex items-center gap-2.5">
            <Calendar className="w-6 h-6 text-rose-500" />
            <span>Event Management & Ticketing</span>
          </h1>
          <p className="text-xs text-slate-600 font-medium mt-1">
            Browse campus gatherings, purchase member-discounted passes, validate QR tickets at the door, and track live attendance.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {canManageEvents && (
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 text-white font-bold text-xs shadow-md shadow-indigo-500/20 hover:opacity-95 transition"
            >
              <Plus className="w-4 h-4" />
              <span>Create Event</span>
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
        <button
          onClick={() => setActiveTab('DISCOVER')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
            activeTab === 'DISCOVER'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200/80 border border-slate-200/80'
          }`}
        >
          All Events ({events.length})
        </button>
        <button
          onClick={() => setActiveTab('MY_TICKETS')}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition ${
            activeTab === 'MY_TICKETS'
              ? 'bg-indigo-600 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200/80 border border-slate-200/80'
          }`}
        >
          My Tickets Wallet ({myTickets.length})
        </button>
        {canScan && (
          <button
            onClick={() => {
              if (events.length > 0 && !selectedEvent) {
                setSelectedEvent(events[0]);
              }
              setActiveTab('SCANNER');
            }}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 ${
              activeTab === 'SCANNER'
                ? 'bg-teal-600 text-white shadow-md shadow-teal-500/20'
                : 'text-teal-700 hover:text-teal-900 bg-teal-50 hover:bg-teal-100 border border-teal-200'
            }`}
          >
            <QrCode className="w-3.5 h-3.5" />
            <span>Door Scanner Console</span>
          </button>
        )}
      </div>

      {/* DISCOVER TAB: Event Cards */}
      {activeTab === 'DISCOVER' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {events.map((evt) => {
            const confirmedCount = evt._count?.tickets || 0;
            const remaining = Math.max(0, evt.capacity - confirmedCount);
            const isSoldOut = remaining === 0 || evt.status === 'SOLD_OUT';

            return (
              <div
                key={evt.id}
                className="glass-panel rounded-2xl border border-brand-500/20 overflow-hidden flex flex-col justify-between glass-panel-hover"
              >
                <div>
                  <div className="h-40 relative bg-navy-900 overflow-hidden">
                    <img
                      src={
                        evt.bannerUrl ||
                        'https://images.unsplash.com/photo-1540575467063-178a50c2df87?w=800'
                      }
                      alt={evt.title}
                      className="w-full h-full object-cover"
                    />
                    <div className="absolute top-3 right-3 flex gap-1.5">
                      <span className="text-[10px] bg-navy-950/80 backdrop-blur-md text-brand-300 font-bold px-2.5 py-1 rounded-full border border-brand-500/30">
                        {evt.category}
                      </span>
                      <span
                        className={`text-[10px] font-bold px-2.5 py-1 rounded-full backdrop-blur-md ${
                          isSoldOut
                            ? 'bg-red-950/80 text-red-300 border border-red-500/30'
                            : 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/30'
                        }`}
                      >
                        {isSoldOut ? 'SOLD OUT' : evt.status}
                      </span>
                    </div>
                  </div>

                  <div className="p-5">
                    <h2 className="text-base font-bold text-white line-clamp-1">{evt.title}</h2>
                    <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                      {evt.description}
                    </p>

                    <div className="mt-4 space-y-2 text-xs text-slate-300">
                      <div className="flex items-center gap-2">
                        <Clock className="w-3.5 h-3.5 text-brand-400" />
                        <span>{new Date(evt.startDate).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <MapPin className="w-3.5 h-3.5 text-teal-400" />
                        <span className="truncate">{evt.venue}</span>
                      </div>
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-slate-400">Seat Capacity:</span>
                        <span className="font-semibold text-slate-200">
                          {confirmedCount} / {evt.capacity} booked ({remaining} left)
                        </span>
                      </div>
                    </div>

                    {/* Progress Bar for Seat Fill */}
                    <div className="w-full h-1.5 bg-slate-800 rounded-full mt-2 overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-brand-500 to-teal-400 rounded-full"
                        style={{ width: `${Math.min(100, (confirmedCount / evt.capacity) * 100)}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Bottom Ticket Prices & Book Action */}
                <div className="p-5 pt-0">
                  <div className="p-3 rounded-xl bg-navy-900/90 border border-slate-800 flex items-center justify-between text-xs mb-3">
                    <div>
                      <div className="text-[10px] text-slate-400 uppercase font-semibold">Pricing</div>
                      <div className="text-teal-400 font-bold">
                        Member: ${evt.ticketTypes[0]?.memberPrice ?? 0}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-[10px] text-slate-400 uppercase font-semibold">Non-Member</div>
                      <div className="text-slate-300 font-semibold">
                        ${evt.ticketTypes[0]?.nonMemberPrice ?? 0}
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        setSelectedEvent(evt);
                        setSelectedTicketType(evt.ticketTypes[0] || null);
                        setIsBookModalOpen(true);
                      }}
                      disabled={isSoldOut}
                      className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-brand-600 to-teal-600 hover:opacity-95 text-white font-semibold text-xs shadow-md shadow-brand-500/20 disabled:opacity-50 transition"
                    >
                      {isSoldOut ? 'Sold Out' : 'Book Ticket'}
                    </button>
                    {canScan && (
                      <button
                        onClick={() => {
                          setSelectedEvent(evt);
                          setActiveTab('SCANNER');
                        }}
                        className="px-3 py-2.5 rounded-xl bg-navy-800 hover:bg-slate-800 text-teal-400 border border-slate-700 text-xs font-semibold"
                        title="Open Scanner for this event"
                      >
                        <QrCode className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* MY TICKETS WALLET TAB */}
      {activeTab === 'MY_TICKETS' && (
        <div className="space-y-4">
          {myTickets.length === 0 ? (
            <div className="bg-white p-8 text-center rounded-2xl border border-slate-200 shadow-sm">
              <TicketIcon className="w-10 h-10 text-slate-400 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-700">No tickets found in your wallet</p>
              <p className="text-xs text-slate-500 mt-1">Book an event ticket above to receive your verified QR pass.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {myTickets.map((t) => (
                <div
                  key={t.id}
                  className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition relative overflow-hidden"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[10px] font-bold text-teal-700 bg-teal-50 px-2.5 py-0.5 rounded-full border border-teal-200 uppercase">
                        {t.ticketType?.name || 'Admission Pass'}
                      </span>
                      <h3 className="text-base font-extrabold text-slate-900 mt-2">{t.event?.title}</h3>
                      <div className="text-xs text-slate-500 mt-1 flex items-center gap-2">
                        <MapPin className="w-3.5 h-3.5 text-slate-400" />
                        <span>{t.event?.venue}</span>
                      </div>
                    </div>

                    <span
                      className={`text-[10px] font-bold px-2.5 py-1 rounded-full ${
                        t.isCheckedIn
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : t.status === 'CANCELLED'
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                      }`}
                    >
                      {t.isCheckedIn ? 'CHECKED IN ✅' : t.status}
                    </span>
                  </div>

                  {/* QR Matrix Representation */}
                  <div className="mt-4 p-4 rounded-xl bg-slate-50 border border-slate-200 flex items-center gap-4">
                    <div className="w-20 h-20 bg-white p-1 rounded-xl flex items-center justify-center shadow-sm border border-slate-200 shrink-0">
                      <TicketQrCodeView ticket={t} />
                    </div>

                    <div className="text-xs space-y-1 min-w-0 flex-1">
                      <div className="text-[10px] text-slate-500 uppercase font-semibold">Ticket Code:</div>
                      <div className="font-mono text-sm font-bold text-indigo-600 select-all truncate">
                        {t.ticketCode}
                      </div>
                      <div className="text-[11px] text-slate-700">Attendee: <strong>{t.attendeeName}</strong></div>
                      {t.booking && (
                        <div className="text-[10px] text-slate-500">Ref: {t.booking.bookingReference}</div>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          setScanTicketCode(t.ticketCode);
                          if (events.length > 0 && (!selectedEvent || selectedEvent.id !== t.eventId)) {
                            const ev = events.find((e) => e.id === t.eventId);
                            if (ev) setSelectedEvent(ev);
                          }
                          setActiveTab('SCANNER');
                        }}
                        className="text-[11px] font-semibold text-teal-600 hover:text-teal-700 underline flex items-center gap-1 pt-1"
                      >
                        <span>Test in Door Scanner</span>
                        <span>→</span>
                      </button>
                    </div>
                  </div>

                  {/* Cancellation option if not used */}
                  {!t.isCheckedIn && t.status === 'VALID' && t.booking && (
                    <div className="mt-3 pt-3 border-t border-slate-100 flex justify-end">
                      <button
                        onClick={() => handleCancelBooking(t.bookingId)}
                        className="text-[11px] text-rose-600 hover:text-rose-700 font-semibold transition flex items-center gap-1"
                      >
                        <RotateCcw className="w-3 h-3" />
                        <span>Cancel Booking & Release Seat</span>
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SCANNER CONSOLE TAB (CRITICAL COMPETITION DEMO WORKFLOW) */}
      {activeTab === 'SCANNER' && (
        <div className="bg-white p-6 sm:p-8 rounded-2xl border border-slate-200 shadow-md max-w-2xl mx-auto space-y-6">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-[10px] font-bold text-teal-700 bg-teal-50 px-2.5 py-0.5 rounded-full border border-teal-200 uppercase tracking-widest">
                DOOR SCANNER CONSOLE
              </span>
              <span className="text-xs text-slate-500 font-medium">Staff Mode: {role}</span>
            </div>
            <h2 className="text-xl font-extrabold text-slate-900">Live Event Ticket Validation</h2>
            <p className="text-xs text-slate-600 mt-1">
              Validates ticket code against event registration, checks membership status, prevents duplicate entry, and marks ticket as USED.
            </p>
          </div>

          {/* Select Target Event */}
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">Target Event</label>
            <select
              value={selectedEvent?.id || ''}
              onChange={(e) => setSelectedEvent(events.find((evt) => evt.id === e.target.value) || null)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 border border-slate-300 text-xs text-slate-800 font-medium focus:outline-none focus:border-teal-500 focus:bg-white transition"
            >
              {events.map((evt) => (
                <option key={evt.id} value={evt.id}>
                  {evt.title} ({evt.venue})
                </option>
              ))}
            </select>
          </div>

          {/* Scanner Simulation Input */}
          <form onSubmit={handleCheckIn} className="space-y-3">
            <label className="block text-xs font-semibold text-slate-700">
              Scan or Enter Ticket Code:
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g. TKT-ABCDE-1234 or paste QR payload"
                value={scanTicketCode}
                onChange={(e) => setScanTicketCode(e.target.value)}
                className="flex-1 px-4 py-2.5 rounded-xl bg-slate-50 border border-slate-300 font-mono text-sm text-slate-900 focus:outline-none focus:border-teal-500 focus:bg-white transition"
              />
              <button
                type="submit"
                className="px-5 py-2.5 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-bold text-xs shadow-md shadow-teal-600/20 transition flex items-center gap-2"
              >
                <CheckCircle className="w-4 h-4" />
                <span>Validate & Admit</span>
              </button>
            </div>
          </form>

          {/* Verification Feedback Banner */}
          {scanResult && (
            <div
              className={`p-5 rounded-2xl border transition-all ${
                scanResult.validationStatus === 'SUCCESS'
                  ? 'bg-emerald-50 border-emerald-200'
                  : scanResult.validationStatus === 'ALREADY_USED'
                  ? 'bg-amber-50 border-amber-200'
                  : 'bg-rose-50 border-rose-200'
              }`}
            >
              <div className="flex items-center gap-3">
                {scanResult.validationStatus === 'SUCCESS' && (
                  <CheckCircle className="w-8 h-8 text-emerald-600 shrink-0" />
                )}
                {scanResult.validationStatus === 'ALREADY_USED' && (
                  <AlertTriangle className="w-8 h-8 text-amber-600 shrink-0" />
                )}
                {scanResult.validationStatus !== 'SUCCESS' &&
                  scanResult.validationStatus !== 'ALREADY_USED' && (
                    <XCircle className="w-8 h-8 text-rose-600 shrink-0" />
                  )}

                <div>
                  <h3
                    className={`text-base font-bold ${
                      scanResult.validationStatus === 'SUCCESS'
                        ? 'text-emerald-900'
                        : scanResult.validationStatus === 'ALREADY_USED'
                        ? 'text-amber-900'
                        : 'text-rose-900'
                    }`}
                  >
                    {scanResult.message}
                  </h3>
                  <div className="text-xs text-slate-600 mt-1">
                    Status: <strong className="font-mono uppercase">{scanResult.validationStatus}</strong>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Book Ticket Modal */}
      <Modal
        isOpen={isBookModalOpen}
        onClose={() => setIsBookModalOpen(false)}
        title={`Book Tickets: ${selectedEvent?.title}`}
        subtitle="Validate membership discount, reserve seat capacity, and generate encrypted QR pass."
      >
        <form onSubmit={handleBook} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-300 mb-1">Ticket Category</label>
            <select
              value={selectedTicketType?.id || ''}
              onChange={(e) =>
                setSelectedTicketType(
                  selectedEvent?.ticketTypes.find((t) => t.id === e.target.value) || null
                )
              }
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            >
              {selectedEvent?.ticketTypes.map((tt) => (
                <option key={tt.id} value={tt.id}>
                  {tt.name} — Member: ${tt.memberPrice} | Non-Member: ${tt.nonMemberPrice}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Attendee Name</label>
              <input
                type="text"
                required
                value={attendeeName}
                onChange={(e) => setAttendeeName(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Attendee Email</label>
              <input
                type="email"
                required
                value={attendeeEmail}
                onChange={(e) => setAttendeeEmail(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              />
            </div>
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Quantity (Max 5)</label>
            <input
              type="number"
              min={1}
              max={5}
              value={bookingQty}
              onChange={(e) => setBookingQty(Number(e.target.value))}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div className="p-3 rounded-xl bg-navy-950 border border-slate-800 text-xs flex justify-between items-center">
            <span className="text-slate-400">Total Price:</span>
            <span className="font-extrabold text-teal-400 text-sm">
              ${(selectedTicketType?.memberPrice || 10) * bookingQty} USD
            </span>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsBookModalOpen(false)}
              className="px-3 py-2 rounded-xl bg-slate-800 text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-gradient-to-r from-brand-600 to-teal-600 text-white font-semibold"
            >
              Confirm Booking & Generate QR
            </button>
          </div>
        </form>
      </Modal>

      {/* Create Event Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Publish New Society Event"
        subtitle="Establish registration limits, member discount tiers, and venue information."
      >
        <form onSubmit={handleCreateEvent} className="space-y-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-300 mb-1">Event Title</label>
            <input
              type="text"
              required
              placeholder="e.g. Skyline Hackathon & Cultural Showcase"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-300 mb-1">Description</label>
            <textarea
              rows={3}
              required
              placeholder="Keynote talks, project exhibitions, catered banquet..."
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Venue / Room</label>
              <input
                type="text"
                required
                value={newVenue}
                onChange={(e) => setNewVenue(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Capacity (Seats)</label>
              <input
                type="number"
                min={1}
                required
                value={newCapacity}
                onChange={(e) => setNewCapacity(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Member Price ($)</label>
              <input
                type="number"
                min={0}
                required
                value={newMemberPrice}
                onChange={(e) => setNewMemberPrice(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              />
            </div>
            <div>
              <label className="block font-semibold text-slate-300 mb-1">Non-Member Price ($)</label>
              <input
                type="number"
                min={0}
                required
                value={newNonMemberPrice}
                onChange={(e) => setNewNonMemberPrice(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-xl bg-navy-950 border border-slate-700 text-white"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setIsCreateModalOpen(false)}
              className="px-3 py-2 rounded-xl bg-slate-800 text-slate-300"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-5 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-semibold"
            >
              Publish Event
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
