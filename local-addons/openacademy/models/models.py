# -*- coding: utf-8 -*-

from openerp import models, fields, api, exceptions, _
from datetime import timedelta


class Course(models.Model):
    _name = 'openacademy.course'

    name = fields.Char(string='Title', required=True)
    description = fields.Text()

    responsible_id = fields.Many2one('res.users', ondelete='set null', string='Responsible', index=True)
    session_ids = fields.One2many(comodel_name="openacademy.session", inverse_name="course_id", string="Sessions",
                                  required=False, )

    @api.multi
    def copy(self, default=None):
        """
        Re-implement "copy" method which allows to duplicate the Course object, changing the original name
        into "Copy of [original name]"
        :return:
        """
        default = dict(default or {})
        copied_count = self.search_count([('name', '=like', _(u"Copy of {}%").format(self.name))])
        print copied_count
        if not copied_count:
            new_name = _(u"Copy of {}").format(self.name)
        else:
            new_name = _(u"Copy of {} ({})").format(self.name, copied_count)

        default['name'] = new_name
        return super(Course, self).copy(default)

    """
    1- Check that the course description and the course title are different
    2- Make the course's name UNIQUE
    """
    _sql_constraints = [
        ('name_description_check',
         'CHECK(name != description)',
         "The title of the course should not be the description"),

        ('name_unique',
         'UNIQUE(name)',
         "The course title must be unique")
    ]


class Session(models.Model):
    _name = 'openacademy.session'

    name = fields.Char(required=True)
    start_date = fields.Date(default=fields.Date.today)
    duration = fields.Float(digits=(6, 2), help="Duration in days")
    seats = fields.Integer(string="Number of seats")
    active = fields.Boolean(default=True)
    instructor_id = fields.Many2one(comodel_name="res.partner", string="Instructor", required=False,
                                    domain=['|', ('instructor', '=', True),
                                            ('category_id.name', 'ilike', 'Teacher')])

    course_id = fields.Many2one(comodel_name="openacademy.course", string="Course", required=True, ondelete='cascade')
    attendee_ids = fields.Many2many('res.partner', string="Attendees")

    taken_seats = fields.Float(string='Taken seats', compute='_taken_seats')

    end_date = fields.Date(string="End Date", store=True, compute='_get_end_date', inverse='_set_end_date')

    hours = fields.Float(string="Duration in hours", compute='_get_hours', inverse='_set_hours')

    attendees_count = fields.Integer(string="Attendees count", compute='_get_attendees_count', store=True)

    # Save color for kanban view
    color = fields.Integer()

    # Workflow like
    state = fields.Selection([
        ('draft', "Draff"),
        ('confirmed', "Confirmed"),
        ('done', "Done"),
    ])

    @api.multi
    def action_draft(self):
        self.state = 'draft'

    @api.multi
    def action_confirm(self):
        self.state = 'confirmed'

    @api.multi
    def action_done(self):
        self.state = 'done'

    @api.depends('seats', 'attendee_ids')
    def _taken_seats(self):
        for r in self:
            if not r.seats:
                r.taken_seats = 0.0
            else:
                r.taken_seats = 100.0 * len(r.attendee_ids) / r.seats

    @api.depends('start_date', 'duration')
    def _get_end_date(self):
        for r in self:
            if not (r.start_date and r.duration):
                r.end_date = r.start_date
                continue
            """
            Add duration to start_date, but: Monday + 5 days = Saturday, so
            subtract one second to get on Friday instead
            """
            start = fields.Datetime.from_string(r.start_date)
            duration = timedelta(days=r.duration, seconds=-1)
            r.end_date = start + duration

    def _set_end_date(self):
        for r in self:
            if not (r.start_date and r.end_date):
                continue
            """
            Compute the defference between dates, but: Friday - Monday = 4 days,
            so add one day to get 5 day instead
            """
            start_date = fields.Datetime.from_string(r.start_date)
            end_date = fields.Datetime.from_string(r.end_date)
            r.duration = (end_date - start_date).days + 1

    @api.depends('duration')
    def _get_hours(self):
        """
        Tra ve gia tri cho compute field hours
        :return:
        """
        for r in self:
            r.hours = r.duration * 24

    def _set_hours(self):
        """
        Ham set gia tri cho compute field hours
        :return:
        """
        for r in self:
            r.duration = r.hours / 24

    @api.depends('attendee_ids')
    def _get_attendees_count(self):
        for r in self:
            r.attendees_count = len(r.attendee_ids)

    @api.onchange('seats', 'attendee_ids')
    def _verify_valid_seats(self):
        """
        Dam bao so cho ngoi khong bi vuot qua
        :return:
        """
        if self.seats < 0:
            return {
                'warning': {
                    'title': _("Incorrect 'seats' value"),
                    'message': _("The number of available seats may not be negative"),
                }
            }
        if self.seats < len(self.attendee_ids):
            return {
                'warning': {
                    'title': _("Too many attendees"),
                    'message': _("Increase seats or remove excess attendees")
                }
            }

    @api.constrains('instructor_id', 'attendee_ids')
    def _check_instrcutor_not_in_attendees(self):
        """
        Checks that the instructor is not present in the attendees of his/her own session
        :return:
        """
        for r in self:
            if r.instructor_id and r.instructor_id in r.attendee_ids:
                raise exceptions.ValidationError(_("A session's instrcutor can't be an attendee"))
